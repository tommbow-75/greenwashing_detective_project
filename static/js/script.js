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

// --- 第一部分：資料搜尋與篩選 (Search & Filter) ---

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

// --- 第二部分：公司列表顯示 (List View) ---

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

    pageData.forEach(company => {
        // 判斷風險等級顏色 (分數越高越好/越綠)
        // 根據 Python 邏輯: Score 是百分比。
        const totalRisk = getRiskColor(company.greenwashingScore);
        const eLevel = getRiskColor(company.eScore);
        const sLevel = getRiskColor(company.sScore);
        const gLevel = getRiskColor(company.gScore);
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

        // 綁定點擊事件
        tr.onclick = () => showDetail(company);

        container.appendChild(tr);
    });
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

// 輔助函式：取得表格中的風險顏色 (與 getRiskLabel 類似但返回物件)
function getRiskColor(score) {
    // 確保 score 是數字
    const num = parseFloat(score);
    // 假設: 0-25 高風險(紅), 26-50 中風險(黃), 51-75 低風險(橘), >75 無風險(綠)
    if (num <= 25) return { text: '高', color: 'red' };
    if (num <= 50) return { text: '中', color: 'orange' };
    if (num <= 75) return { text: '低', color: '#d4ac0d' };
    return { text: '無', color: 'green' };
};

// --- 第三部分：詳細視圖 (Detail View) ---

// 顯示詳細視圖
function showDetail(company) {
    currentCompany = company;
    currentField = null;
    document.getElementById('filterHint').style.display = 'none';
    document.getElementById('detailCompanyName').textContent = `${company.name} - 詳細分析 (${company.year}年)`;

    // 依序執行渲染
    renderLayer4(company);
    renderLayer5(company); // [New] 新增 Layer 5 的渲染
    renderLayer6(company);
    generateWordcloud(company); // 文字雲放到最後

    document.querySelectorAll('.analysis-section').forEach(el => {
        el.classList.remove('hidden');
    });

    document.getElementById('detailView').classList.add('active');
    window.scrollTo({ top: 0, behavior: 'smooth' });
}

// 關閉詳細視圖
function closeDetail() {
    currentCompany = null;
    document.getElementById('detailView').classList.remove('active');
    // 如果需要清空內容可以加：
    // document.getElementById('layer4Table').innerHTML = '';
    // document.getElementById('layer5Table').innerHTML = '';
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

// [Layer 4] 內部比對
function renderLayer4(company) {
    const tableBody = document.getElementById('layer4Table');
    tableBody.innerHTML = '';

    if (!company.layer4Data || company.layer4Data.length === 0) {
        tableBody.innerHTML = '<tr><td colspan="6" style="text-align:center;">無資料</td></tr>';
        return;
    }

    company.layer4Data.forEach(row => {
        // 1. 計算調整後的分數 (Net Score)
        const initialRisk = parseFloat(row.risk_score) || 0;
        // const deduction = parseFloat(row.adjustment_score) || 0;
        // 分數最低扣到 0，不出現負分
        // const netScore = Math.max(0, initialRisk - deduction).toFixed(1);

        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td>${row.ESG_category || ''}</td>
            <td title="${row.SASB_topic}">${row.SASB_topic || ''}</td> 
            <td>${row.page_number || '-'}</td>
            <td title="${row.report_claim}">${cutString(row.report_claim, 15)}</td>
            
            <td style="color: #666; font-size: 0.9em;">
                ${row.greenwashing_factor || '-'}
            </td>

            <td>${getRiskLabel(initialRisk)}</td>
        `;
        tableBody.appendChild(tr);
    });
}

// [Layer 5] 外部新聞揭露對比
function renderLayer5(company) {
    const tableBody = document.getElementById('layer5Table');
    tableBody.innerHTML = '';

    const dataWithEvidence = company.layer4Data;

    if (!dataWithEvidence || dataWithEvidence.length === 0) {
        tableBody.innerHTML = '<tr><td colspan="7" style="text-align:center;">無相關外部證據資料</td></tr>';
        return;
    }

    dataWithEvidence.forEach(row => {
        // 計算 Net Score
        const initialRisk = parseFloat(row.risk_score) || 0;
        const deduction = parseFloat(row.adjustment_score) || 0;
        const netScore = Math.max(0, initialRisk - deduction).toFixed(1);

        const evidence = row.external_evidence || '-';
        const status = row.consistency_status || '待確認';
        const msci = row.MSCI_flag || '-';
        const url = row.external_evidence_url ? `<a href="${row.external_evidence_url}" target="_blank">連結</a>` : '-';

        let statusColor = 'black';
        if (status.includes('不一致')) statusColor = 'var(--danger)';
        else if (status.includes('一致')) statusColor = 'var(--success)';

        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td>${row.ESG_category}</td>
            <td title="${row.report_claim}">${cutString(row.report_claim, 15)}</td>
            <td title="${evidence}">${cutString(evidence, 15)}</td>
            <td>${url}</td>
            <td style="color:${statusColor}; font-weight:bold;">${status}</td>
            <td>${msci}</td>
            
            <td>${getRiskLabel(netScore)}</td>
        `;
        tableBody.appendChild(tr);
    });
}

// [Layer 6] SASB 產業權重分布
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

// [Layer 7] 文字雲生成
function generateWordcloud(company) {
    const wordcloudArea = document.getElementById('wordcloudArea');

    // Dispose existing chart if any, to avoid memory leaks or conflicts
    const existingChart = echarts.getInstanceByDom(wordcloudArea);
    if (existingChart) {
        existingChart.dispose();
    }

    wordcloudArea.innerHTML = '';
    // Set explicit dimensions for Echarts
    wordcloudArea.style.width = '100%';
    wordcloudArea.style.height = '500px';

    // Error handling if stockId or year is missing
    if (!company.stockId || !company.year) {
        console.warn('generateWordcloud: Missing stockId or year', company);
        wordcloudArea.innerHTML = '<div style="padding:1rem; color: #666;">無法顯示文字雲：資料缺漏 (StockID 或 Year)</div>';
        wordcloudArea.style.height = 'auto';
        return;
    }

    const stockId = String(company.stockId).trim();
    const year = String(company.year).trim();

    // Construct path to JSON
    // Note: User mentioned file name format 1102_2024_wc.json
    const jsonPath = `/wordcloud/${stockId}_${year}_wc.json`;
    console.log(`[WordCloud] Attempting to load JSON: ${jsonPath}`, { stockId, year });

    // Show loading state
    wordcloudArea.innerHTML = '<div style="display:flex; justify-content:center; align-items:center; height:100%; color:#666;">載入文字雲中...</div>';

    fetch(jsonPath)
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            // Clear loading message
            wordcloudArea.innerHTML = '';

            const chart = echarts.init(wordcloudArea);

            // Determine size range based on screen width
            const isDesktop = window.innerWidth > 768;
            const sizeRange = isDesktop ? [30, 90] : [12, 50];

            const option = {
                tooltip: {
                    show: true,
                    formatter: '{b}: {c}'
                },
                series: [{
                    type: 'wordCloud',
                    shape: 'circle',
                    left: 'center',
                    top: 'center',
                    width: '95%',
                    height: '95%',
                    right: null,
                    bottom: null,
                    sizeRange: sizeRange,
                    rotationRange: [-45, 90],
                    rotationStep: 45,
                    gridSize: 8,
                    drawOutOfBound: false,
                    layoutAnimation: true,
                    textStyle: {
                        fontFamily: 'sans-serif',
                        fontWeight: 'bold',
                        color: function () {
                            // Random colors
                            return 'rgb(' + [
                                Math.round(Math.random() * 160),
                                Math.round(Math.random() * 160),
                                Math.round(Math.random() * 160)
                            ].join(',') + ')';
                        }
                    },
                    emphasis: {
                        focus: 'self',
                        textStyle: {
                            shadowBlur: 10,
                            shadowColor: '#333'
                        }
                    },
                    data: data
                }]
            };

            chart.setOption(option);

            // Handle window resize
            window.addEventListener('resize', function () {
                chart.resize();

                // 動態調整文字大小範圍
                const newIsDesktop = window.innerWidth > 768;
                const newSizeRange = newIsDesktop ? [30, 90] : [12, 50];

                chart.setOption({
                    series: [{
                        sizeRange: newSizeRange
                    }]
                });
            });
        })
        .catch(err => {
            console.error('[WordCloud] Load failed:', err);
            wordcloudArea.innerHTML = `<div style="padding:1rem; color: #666; display:flex; flex-direction:column; align-items:center; justify-content:center; height:100%;">
                <p>無法載入文字雲資料</p>
                <small style="color:#999">(${stockId}_${year}_wc.json)</small>
            </div>`;
        });
}

// --- 輔助函式與資料讀取 (Helpers & Data) ---

// 讀取 SASB JSON
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

// 輔助函式：截斷字串
function cutString(str, len) {
    if (!str) return '-';
    if (str.length <= len) return str;
    return str.substring(0, len) + '...';
}

// 輔助函式：取得風險標籤 (支援小數點判斷)
// 邏輯：分數越高越安全(綠)，越低越危險(紅)
function getRiskLabel(score) {
    const numScore = parseFloat(score); // 確保是數字

    // 防呆：若非數字則回傳原始值
    if (isNaN(numScore)) return score;

    let labelClass = '';
    let labelText = '';

    // 定義分數區間
    // >= 3.5 : 無風險 (綠)
    // >= 2.5 : 低風險 (黃)
    // >= 1.5 : 中風險 (橘)
    // < 1.5  : 高風險 (紅)

    if (numScore >= 3.5) {
        labelClass = 'no';
        labelText = `無風險 (${numScore})`;
    } else if (numScore >= 2.5) {
        labelClass = 'low';
        labelText = `低風險 (${numScore})`;
    } else if (numScore >= 1.5) {
        labelClass = 'medium';
        labelText = `中風險 (${numScore})`;
    } else {
        labelClass = 'high';
        labelText = `高風險 (${numScore})`;
    }

    return `<span class="risk-label ${labelClass}">${labelText}</span>`;
}