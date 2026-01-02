// --- 全域變數宣告 ---
// 注意：companiesData 已經由 HTML 透過 Jinja2 傳入，這裡不需要再次宣告，否則會報錯。
let sasbRawData = [];
let SASB_TOPICS = [];

let currentCompany = null;
let currentField = null;

// 分頁相關變數
let currentPage = 1; // 目前頁面
const itemsPerPage = 20; // 每頁顯示20筆
let filteredData = []; // 搜尋過後的資料會存在這

// --- 初始化 ---
// 確保 HTML 載入完成後才執行 JS
document.addEventListener('DOMContentLoaded', async () => {
    console.log("App initialized.");

    // 檢查資料是否成功從後端傳入
    if (typeof companiesData === 'undefined' || !companiesData) {
        console.error("錯誤：無法讀取 companiesData。請確認 HTML 是否正確注入資料。");
        return;
    }

    // 預設顯示所有資料
    filteredData = companiesData;

    // 1. 先載入 SASB 設定檔 (用於顯示詳細頁的權重圖)
    await loadSasbData();

    // 2. 設置按鈕事件監聽
    setupEventListeners();

    // 3. (選擇性) 如果想要一進來就顯示列表，可以打開下面這行
    // renderCompanies(companiesData);
});

// --- 讀取 JSON 的函式 ---
async function loadSasbData() {
    try {
        // 使用正確的 JSON 路徑
        const response = await fetch(sasbJsonPath);

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        sasbRawData = await response.json();

        // 解析資料，生成議題列表
        if (sasbRawData.length > 0) {
            SASB_TOPICS = sasbRawData.map(item => item["議題"]);
            console.log("SASB 資料載入成功:", sasbRawData.length, "筆資料");
        }

    } catch (error) {
        console.warn("注意：SASB_weightMap.json 讀取失敗，可能是路徑錯誤或檔案不存在。", error);
        // 即使讀取失敗，也不要讓程式當機，僅顯示警告
        document.getElementById('sasbContainer').innerHTML = '<div style="padding:1rem">無法載入產業權重地圖 (JSON 讀取失敗)</div>';
    }
}

// 渲染公司列表 (Table Row) - 支援分頁
function renderCompanies(data) {
    const container = document.getElementById('companiesContainer');
    container.innerHTML = '';

    if (!data || data.length === 0) {
        container.innerHTML = '<tr><td colspan="9" style="text-align:center; padding: 2rem;">查無資料</td></tr>';
        document.getElementById('paginationControls').style.display = 'none';
        return;
    }

    // 計算分頁
    const totalPages = Math.ceil(data.length / itemsPerPage);
    const startIndex = (currentPage - 1) * itemsPerPage;
    const endIndex = startIndex + itemsPerPage;
    const pageData = data.slice(startIndex, endIndex);

    // 更新分頁控制
    updatePaginationControls(totalPages);

    const getScoreLevel = (score) => {
        // 確保 score 是數字
        const num = parseFloat(score);
        // 假設: 0-25 高風險(紅), 26-50 中風險(黃), 51-75 低風險(橘), >75 無風險(綠)
        if (num <= 25) return { text: '高', color: 'red' };
        if (num <= 50) return { text: '中', color: 'orange' };
        if (num <= 75) return { text: '低', color: '#d4ac0d' };
        return { text: '無', color: 'green' };
    };

    // 這裡先假設後端有算好的分數，直接抓來用

    pageData.forEach(company => {
        // 判斷風險等級顏色 (分數越高越好/越綠)
        // 根據 Python 邏輯: Score 是百分比。
        const totalRisk = getScoreLevel(company.greenwashingScore);
        const eLevel = getScoreLevel(company.eScore);
        const sLevel = getScoreLevel(company.sScore);
        const gLevel = getScoreLevel(company.gScore);
        const indName = company.industry;

        const tr = document.createElement('tr');
        tr.style.textAlign = 'center';
        tr.style.cursor = 'pointer';
        tr.style.borderBottom = '1px solid #eee';

        tr.innerHTML = `
            <td style="padding: 1rem; font-weight: bold; color: var(--primary);">${company.name}</td>
            <td style="padding: 1rem;">${company.stockId || '-'}</td>
            <td style="padding: 1rem;">${company.industry}</td>
            <td style="padding: 1rem;">${company.year}</td>
            <td style="padding: 1rem;color: ${totalRisk.color}; font-weight: bold;">${totalRisk.text}</td>
            <td style="padding: 1rem;color: ${eLevel.color};">${eLevel.text}</td>
            <td style="padding: 1rem;color: ${sLevel.color};">${sLevel.text}</td>
            <td style="padding: 1rem;color: ${gLevel.color};">${gLevel.text}</td>
            <td style="padding: 1rem;">
                <button class="btn" style="padding: 5px 10px; font-size: 0.8rem;">查看詳情</button>
            </td>
        `;

        // 綁定點擊事件 (注意這裡不能直接 onclick="showDetail" 因為傳遞物件會有引號問題)
        tr.onclick = () => showDetail(company);

        container.appendChild(tr);
    });
}

// 顯示詳細視圖
function showDetail(company) {
    currentCompany = company;
    currentField = null;
    document.getElementById('filterHint').style.display = 'none';
    document.getElementById('detailCompanyName').textContent = `${company.name} - 詳細分析 (${company.year}年)`;

    generateWordcloud(company); // 呼叫亂數文字雲
    renderLayer4(company);
    renderLayer6(company);      // 顯示 SASB 地圖

    document.querySelectorAll('.analysis-section').forEach(el => {
        el.classList.remove('hidden');
    });

    document.getElementById('detailView').classList.add('active');
    window.scrollTo({ top: 0, behavior: 'smooth' });
}

function closeDetail() {
    document.getElementById('detailView').classList.remove('active');
    currentCompany = null;
}

function filterByField(field) {
    // 前端篩選詳細頁籤 (E/S/G) 的功能
    const fieldMap = { 'E': '環境', 'S': '社會', 'G': '治理' };
    currentField = field;
    document.getElementById('filterHint').style.display = 'block';
    document.getElementById('filterFieldName').textContent = fieldMap[field];

    document.querySelectorAll('.analysis-section').forEach(el => {
        el.classList.add('hidden');
    });

    // 顯示特定區塊 (這裡依需求調整顯示哪些層)
    document.getElementById('layer4').classList.remove('hidden');
    // document.getElementById('layer5').classList.remove('hidden');
}

function clearFilter() {
    currentField = null;
    document.getElementById('filterHint').style.display = 'none';
    document.querySelectorAll('.analysis-section').forEach(el => {
        el.classList.remove('hidden');
    });
}

// [修改點 A] 改寫文字雲生成邏輯：先使用亂數假資料
function generateWordcloud(company) {
    const wordcloudArea = document.getElementById('wordcloudArea');
    wordcloudArea.innerHTML = '';

    // Error handling if stockId or year is missing
    if (!company.stockId || !company.year) {
        wordcloudArea.innerHTML = '<div style="padding:1rem; color: #666;">無法顯示文字雲：資料缺漏 (StockID 或 Year)</div>';
        return;
    }

    const imgPath = `/static/images/${company.stockId}_${company.year}_word_cloud.png`;

    const img = document.createElement('img');
    img.src = imgPath;
    img.alt = `${company.name} 文字雲`;
    img.style.maxWidth = '100%';
    img.style.height = 'auto';
    img.style.display = 'block';
    img.style.margin = '0 auto';

    // Simple error handling for image 404
    img.onerror = function () {
        wordcloudArea.innerHTML = '<div style="padding:1rem; color: #666;">尚無此公司的文字雲圖片</div>';
    };

    wordcloudArea.appendChild(img);
}

function renderLayer4(company) {
    const tableBody = document.getElementById('layer4Table');
    tableBody.innerHTML = '';

    // 注意：後端傳來的資料結構要是 list of dicts
    if (!company.layer4Data || company.layer4Data.length === 0) {
        tableBody.innerHTML = '<tr><td colspan="6" style="text-align:center;">無資料</td></tr>';
        return;
    }

    company.layer4Data.forEach(row => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td>${row.category}</td>
            <td>${row.sasb_topic}</td> <td>${row.page_number || '-'}</td>
            <td>${row.report_claim || '-'}</td>
            <td>${row.adjustment_score}</td>
            <td>${getRiskLabel(row.risk_score)}</td>
        `;
        tableBody.appendChild(tr);
    });
}

function getRiskLabel(score) {
    let labelClass = '';
    let labelText = '';
    const numScore = Number(score);

    if (numScore === 4) {
        labelClass = 'no'; labelText = '無風險 (4)';
    } else if (numScore === 3) {
        labelClass = 'low'; labelText = '低風險 (3)';
    } else if (numScore === 2) {
        labelClass = 'medium'; labelText = '中風險 (2)';
    } else if (numScore <= 1) {
        labelClass = 'high'; labelText = '高風險 (' + numScore + ')';
    } else {
        labelClass = 'no'; labelText = numScore;
    }
    return `<span class="risk-label ${labelClass}">${labelText}</span>`;
}

function setupEventListeners() {
    console.log("Setting up event listeners...");
    const searchBtn = document.getElementById('searchButton');
    const searchInput = document.getElementById('searchInput');

    if (searchBtn) {
        searchBtn.addEventListener('click', handleSearch);
    } else {
        console.error("找不到搜尋按鈕 (searchButton)");
    }

    if (searchInput) {
        searchInput.addEventListener('keypress', function (e) {
            if (e.key === 'Enter') {
                handleSearch();
            }
        });
    }

    // 分頁控制
    document.getElementById('prevPage').addEventListener('click', () => {
        if (currentPage > 1) {
            currentPage--;
            renderCompanies(filteredData);
            window.scrollTo({ top: 0, behavior: 'smooth' });
        }
    });

    document.getElementById('nextPage').addEventListener('click', () => {
        const totalPages = Math.ceil(filteredData.length / itemsPerPage);
        if (currentPage < totalPages) {
            currentPage++;
            renderCompanies(filteredData);
            window.scrollTo({ top: 0, behavior: 'smooth' });
        }
    });
}

// 處理搜尋按鈕點擊
function handleSearch() {
    console.log("Search triggered.");

    if (currentCompany) {
        closeDetail();
    }

    filterCompanies();

    // 隱藏初始提示，顯示結果
    document.getElementById('initialPrompt').style.display = 'none';
    document.getElementById('resultsDashboard').style.display = 'block';
}

function filterCompanies() {
    const search = document.getElementById('searchInput').value.toLowerCase().trim();
    const industry = document.getElementById('industryFilter').value;
    const year = document.getElementById('yearFilter').value;

    console.log("Filtering:", { search, industry, year });

    // 使用全域的 companiesData (來自 HTML)
    filteredData = companiesData.filter(c => {
        const matchSearch = c.name.toLowerCase().includes(search) ||
            (c.stockId && c.stockId.includes(search));
        const matchIndustry = !industry || c.industry === industry;
        const matchYear = !year || c.year.toString() === year;
        return matchSearch && matchIndustry && matchYear;
    });

    console.log("Filtered results:", filteredData.length);

    // 重置到第一頁
    currentPage = 1;
    renderCompanies(filteredData);
}

// 更新分頁控制
function updatePaginationControls(totalPages) {
    const paginationControls = document.getElementById('paginationControls');
    const pageInfo = document.getElementById('pageInfo');
    const prevButton = document.getElementById('prevPage');
    const nextButton = document.getElementById('nextPage');

    if (totalPages <= 1) {
        // 如果只有一頁或沒資料，通常不顯示分頁，或者顯示但 disable
        if (totalPages === 0) paginationControls.style.display = 'none';
        else paginationControls.style.display = 'flex';
    } else {
        paginationControls.style.display = 'flex';
    }

    pageInfo.textContent = `第 ${currentPage} 頁 / 共 ${totalPages} 頁 (共 ${filteredData.length} 筆)`;

    prevButton.disabled = currentPage === 1;
    nextButton.disabled = currentPage === totalPages || totalPages === 0;

    prevButton.style.opacity = prevButton.disabled ? '0.5' : '1';
    prevButton.style.cursor = prevButton.disabled ? 'not-allowed' : 'pointer';

    nextButton.style.opacity = nextButton.disabled ? '0.5' : '1';
    nextButton.style.cursor = nextButton.disabled ? 'not-allowed' : 'pointer';
}

function renderLayer6(company) {
    const container = document.getElementById('sasbContainer');
    if (!container) return;
    container.innerHTML = '';

    if (sasbRawData.length === 0) {
        container.innerHTML = '<div style="padding:1rem; color: #666;">無法顯示地圖：尚未載入 SASB 設定檔 (JSON)</div>';
        return;
    }

    const indName = company.industry;

    // 從 sasbRawData 找出該產業權重為 2 的所有議題
    // JSON 結構範例: { "面向": "環境", "議題": "溫室氣體排放", "半導體業": 2, ... }
    const heavyWeightTopics = sasbRawData
        .filter(row => row[indName] === 2)
        .map(row => row["議題"]);

    const infoDiv = document.getElementById('sasbInfo');
    if (infoDiv) {
        infoDiv.innerHTML = `🏢 <span style="font-weight:bold; color:var(--primary)">${company.name}</span> &nbsp;|&nbsp; 🏭 產業類別: <span style="font-weight:bold">${indName}</span>`;
    }

    // 使用全域的 SASB_TOPICS 生成格子
    SASB_TOPICS.forEach(topic => {
        const isHeavy = heavyWeightTopics.includes(topic);
        const weightClass = isHeavy ? 'weight-2' : 'weight-1';

        const item = document.createElement('div');
        item.className = `sasb-item ${weightClass}`;
        item.textContent = topic;

        if (isHeavy) {
            item.title = '權重: 2 (高度相關 - 依據 SASB 準則)';
        } else {
            // 檢查 JSON 中是否有該產業欄位，若無則顯示未定義
            const hasIndustryColumn = sasbRawData[0] && sasbRawData[0].hasOwnProperty(indName);
            item.title = hasIndustryColumn ? '權重: 1 (一般相關)' : '權重: 未定義 (JSON中無此產業)';
        }

        container.appendChild(item);
    });
}