// 示意公司資料
const companiesData = [
    {
        id: 1,
        name: '台積電',
        stockId: '2330',
        industry: '半導體業',
        year: 2025,
        greenwashingScore: 28,
        eScore: 32,
        sScore: 25,
        gScore: 28,
        riskLevel: 'low',
        layer4Data: [
            { category: 'E', topic: '溫室氣體排放', page: 'P.12', claim: '「2025年實現50%減排...」', factor: '實際排放↑2%', risk_score: 'low' },
            { category: 'E', topic: '水資源與廢水處理管理', page: 'P.45', claim: '「回收率達90%」', factor: '符合預期', risk_score: 'no' }
        ]
    },
    {
        id: 2,
        name: '聯發科',
        stockId: '2454',
        industry: '半導體業',
        year: 2025,
        greenwashingScore: 52,
        eScore: 58,
        sScore: 48,
        gScore: 50,
        riskLevel: 'medium',
        layer4Data: [
            { category: 'S', topic: '勞工法規', page: 'P.30', claim: '「無重大勞資糾紛」', factor: '有數起訴訟', risk_score: 'medium' },
            { category: 'G', topic: '供應鏈管理', page: 'P.55', claim: '「100%綠色供應鏈」', factor: '部分供應商未達標', risk_score: 'medium' }
        ]
    },
    {
        id: 3,
        name: '中石化',
        stockId: '1314',
        industry: '油電燃氣業',
        year: 2025,
        greenwashingScore: 78,
        eScore: 85,
        sScore: 72,
        gScore: 65,
        riskLevel: 'high',
        layer4Data: [
            { category: 'E', topic: '溫室氣體排放', page: 'P.12', claim: '「2025年實現50%減排目標...」', factor: '實際排放↑15%', risk_score: 'high' },
            { category: 'E', topic: '能源管理', page: 'P.15', claim: '「100%使用綠電」', factor: '範圍定義模糊', risk_score: 'medium' },
            { category: 'E', topic: '廢棄物與有害物質管理', page: 'P.28', claim: '「零廢棄填埋」', factor: '非法傾倒紀錄', risk_score: 'high' }
        ]
    }
];

// --- 全域變數宣告 (等待 JSON 載入) ---
let sasbRawData = [];
let SASB_TOPICS = [];

let currentCompany = null;
let currentField = null;

// 分頁相關變數
let currentPage = 1;
const itemsPerPage = 20;
let filteredData = [];

// --- 初始化 (改為 Async 以等待資料載入) ---
async function init() {
    // 1. 先載入外部 JSON 檔案
    await loadSasbData();
    
    // 2. 資料載入完成後，設置事件監聽器（不自動渲染）
    setupEventListeners();
}

// --- 讀取 JSON 的函式 ---
async function loadSasbData() {
    try {
        // 自動檢測路徑：如果是 file:// 協議則使用相對路徑，否則使用絕對路徑
        const isFileProtocol = window.location.protocol === 'file:';
        const jsonPath = isFileProtocol 
            ? '../static/data/SASB_weightMap.json' 
            : '/static/data/SASB_weightMap.json';
        
        // 發送請求讀取 json 檔案
        const response = await fetch(jsonPath);
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        // 將回應轉換為 JSON 物件
        sasbRawData = await response.json();
        
        // 解析資料後，動態生成所有議題列表
        // 假設 JSON 格式正確且含有 "議題" 欄位
        SASB_TOPICS = sasbRawData.map(item => item["議題"]);
        
        console.log("SASB 資料載入成功:", sasbRawData.length, "筆資料");

    } catch (error) {
        console.error("載入 SASB_weightMap.json 失敗:", error);
        console.error("嘗試的路徑:", window.location.protocol === 'file:' ? '../static/data/SASB_weightMap.json' : '/static/data/SASB_weightMap.json');
        alert("無法讀取 SASB 設定檔，請確認是否透過 Local Server執行。");
    }
}

// 渲染公司列表 (Table Row) - 支援分頁
function renderCompanies(data) {
    const container = document.getElementById('companiesContainer');
    container.innerHTML = '';

    if (data.length === 0) {
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
        if (score <= 25) return { text: '高', color: 'red' };
        if (score <= 50) return { text: '中', color: 'orange' };
        if (score <= 75) return { text: '低', color: '#d4ac0d' };
        return { text: '無', color: 'green' };
    };

    pageData.forEach(company => {
        const totalRisk = getScoreLevel(company.greenwashingScore);
        const eLevel = getScoreLevel(company.eScore);
        const sLevel = getScoreLevel(company.sScore);
        const gLevel = getScoreLevel(company.gScore);
        const indName = company.industry;

        const tr = document.createElement('tr');
        tr.style.textAlign = 'center';
        tr.style.cursor = 'pointer';
        tr.style.borderBottom = '1px solid #eee';
        tr.onmouseover = function () { this.style.backgroundColor = 'rgba(32, 128, 128, 0.05)'; };
        tr.onmouseout = function () { this.style.backgroundColor = ''; };

        tr.innerHTML = `
            <td style="padding: 1rem; font-weight: bold; color: var(--primary);">${company.name}</td>
            <td style="padding: 1rem;">${company.stockId || '-'}</td>
            <td style="padding: 1rem;">${indName}</td>
            <td style="padding: 1rem;">${company.year}</td>
            <td style="padding: 1rem; color: ${totalRisk.color}; font-weight: bold;">${totalRisk.text}</td>
            <td style="padding: 1rem; color: ${eLevel.color}; font-weight: 500;">${eLevel.text}</td>
            <td style="padding: 1rem; color: ${sLevel.color}; font-weight: 500;">${sLevel.text}</td>
            <td style="padding: 1rem; color: ${gLevel.color}; font-weight: 500;">${gLevel.text}</td>
            <td style="padding: 1rem;">
                <button class="btn" style="padding: 5px 10px; font-size: 0.8rem;" onclick="event.stopPropagation(); showDetail(companiesData.find(c => c.id === ${company.id}))">查看詳情</button>
            </td>
        `;

        tr.addEventListener('click', () => showDetail(company));
        container.appendChild(tr);
    });
}

// 顯示詳細視圖
function showDetail(company) {
    currentCompany = company;
    currentField = null;
    document.getElementById('filterHint').style.display = 'none';
    document.getElementById('detailCompanyName').textContent = `${company.name} - 詳細分析 (${company.year}年)`;

    generateWordcloud(company);
    renderLayer4(company);
    renderLayer6(company); // 這裡會使用到已載入的 JSON 資料

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
    const fieldMap = { 'E': '環境', 'S': '社會', 'G': '治理' };
    currentField = field;
    document.getElementById('filterHint').style.display = 'block';
    document.getElementById('filterFieldName').textContent = fieldMap[field];

    document.querySelectorAll('.analysis-section').forEach(el => {
        el.classList.add('hidden');
    });

    document.getElementById('layer4').classList.remove('hidden');
    document.getElementById('layer5').classList.remove('hidden');
}

function clearFilter() {
    currentField = null;
    document.getElementById('filterHint').style.display = 'none';
    document.querySelectorAll('.analysis-section').forEach(el => {
        el.classList.remove('hidden');
    });
}

function generateWordcloud(company) {
    const wordcloudArea = document.getElementById('wordcloudArea');
    wordcloudArea.innerHTML = '';

    const keywords = {
        '台積電': [
            { text: '碳中和', freq: 45 }, { text: '再生能源', freq: 42 }, { text: '淨零排放', freq: 40 },
            { text: '綠色轉型', freq: 38 }, { text: '永續發展', freq: 32 }, { text: '環保投資', freq: 28 },
            { text: '供應鏈', freq: 25 }, { text: '溫室氣體', freq: 22 }, { text: '透明度', freq: 18 }, { text: '驗證', freq: 15 }
        ],
        '聯發科': [
            { text: 'ESG承諾', freq: 35 }, { text: '環保承諾', freq: 32 }, { text: '減排目標', freq: 28 },
            { text: '綠色製造', freq: 25 }, { text: '社會責任', freq: 20 }, { text: '員工關懷', freq: 18 },
            { text: '社區參與', freq: 15 }, { text: '氣候行動', freq: 12 }, { text: '監測', freq: 10 }, { text: '進度', freq: 8 }
        ],
        '中石化': [
            { text: '淨零承諾', freq: 52 }, { text: '能源轉型', freq: 48 }, { text: '碳中和', freq: 45 },
            { text: '綠色企業', freq: 42 }, { text: '環保投資', freq: 38 }, { text: '永續開發', freq: 35 },
            { text: '生物燃料', freq: 32 }, { text: '氣候承諾', freq: 28 }, { text: '社區協和', freq: 22 }, { text: '責任', freq: 18 }
        ]
    };

    const companyWords = keywords[company.name] || keywords['台積電'];
    const maxFreq = Math.max(...companyWords.map(w => w.freq));

    companyWords.forEach(word => {
        const ratio = word.freq / maxFreq;
        let sizeClass = 'low';
        if (ratio > 0.8) sizeClass = 'high';
        else if (ratio > 0.5) sizeClass = 'medium';

        const wordEl = document.createElement('div');
        wordEl.className = `word ${sizeClass}`;
        wordEl.textContent = word.text;
        wordEl.title = `出現頻率: ${word.freq}次`;
        wordcloudArea.appendChild(wordEl);
    });
}

function renderLayer4(company) {
    const tableBody = document.getElementById('layer4Table');
    tableBody.innerHTML = '';

    if (!company.layer4Data || company.layer4Data.length === 0) {
        tableBody.innerHTML = '<tr><td colspan="6" style="text-align:center;">無資料</td></tr>';
        return;
    }

    company.layer4Data.forEach(row => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td>${row.category}</td>
            <td>${row.topic}</td>
            <td>${row.page}</td>
            <td>${row.claim}</td>
            <td>${row.factor}</td>
            <td>${getRiskLabel(row.risk_score)}</td>
        `;
        tableBody.appendChild(tr);
    });
}

function getRiskLabel(score) {
    let labelClass = '';
    let labelText = '';
    const s = String(score).toLowerCase();

    if (s === 'high' || s === '高') {
        labelClass = 'high';
        labelText = '高風險';
    } else if (s === 'medium' || s === '中') {
        labelClass = 'medium';
        labelText = '中風險';
    } else if (s === 'low' || s === '低') {
        labelClass = 'low';
        labelText = '低風險';
    } else {
        labelClass = 'no';
        labelText = '無風險';
    }
    return `<span class="risk-label ${labelClass}">${labelText}</span>`;
}

function setupEventListeners() {
    // 移除自動觸發，改為點擊搜尋按鈕才觸發
    document.getElementById('searchButton').addEventListener('click', handleSearch);
    
    // 支援 Enter 鍵觸發搜尋
    document.getElementById('searchInput').addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            handleSearch();
        }
    });
    
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
    // 關閉詳細視圖（修改點 C）
    if (currentCompany) {
        closeDetail();
    }
    
    // 執行搜尋
    filterCompanies();
    
    // 顯示結果列表，隱藏初始提示
    document.getElementById('initialPrompt').style.display = 'none';
    document.getElementById('resultsDashboard').style.display = 'block';
}

function filterCompanies() {
    let data = companiesData;
    const search = document.getElementById('searchInput').value.toLowerCase();
    const industry = document.getElementById('industryFilter').value;
    const year = document.getElementById('yearFilter').value;

    filteredData = data.filter(c => {
        const matchSearch = c.name.toLowerCase().includes(search);
        const matchIndustry = !industry || c.industry === industry;
        const matchYear = !year || c.year.toString() === year;
        return matchSearch && matchIndustry && matchYear;
    });

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
        paginationControls.style.display = 'none';
    } else {
        paginationControls.style.display = 'flex';
        pageInfo.textContent = `第 ${currentPage} 頁 / 共 ${totalPages} 頁 (共 ${filteredData.length} 筆資料)`;
        
        prevButton.disabled = currentPage === 1;
        nextButton.disabled = currentPage === totalPages;
        
        prevButton.style.opacity = currentPage === 1 ? '0.5' : '1';
        prevButton.style.cursor = currentPage === 1 ? 'not-allowed' : 'pointer';
        
        nextButton.style.opacity = currentPage === totalPages ? '0.5' : '1';
        nextButton.style.cursor = currentPage === totalPages ? 'not-allowed' : 'pointer';
    }
}

function handlePdfUpload(e) {
    const file = e.target.files[0];
    if (file) {
        alert(`已選擇: ${file.name}\n(此為示意，實際應連接後端模型進行分析)`);
    }
}

// --- SASB 資料與渲染 (保持動態邏輯) ---

function renderLayer6(company) {
    const container = document.getElementById('sasbContainer');
    if (!container) return;
    container.innerHTML = '';

    // 檢查資料是否已載入
    if (sasbRawData.length === 0) {
        container.innerHTML = '<div style="padding:1rem">SASB 資料讀取中或讀取失敗...</div>';
        return;
    }

    const indName = company.industry;

    // 從 sasbRawData 找出該產業權重為 2 的所有議題
    const heavyWeightTopics = sasbRawData
        .filter(row => row[indName] === 2)
        .map(row => row["議題"]);

    const infoDiv = document.getElementById('sasbInfo');
    if (infoDiv) {
        infoDiv.innerHTML = `🏢 <span style="font-weight:bold; color:var(--primary)">${company.name}</span> &nbsp;|&nbsp; 🏭 產業類別: <span style="font-weight:bold">${indName}</span>`;
    }

    SASB_TOPICS.forEach(topic => {
        const isHeavy = heavyWeightTopics.includes(topic);
        const weightClass = isHeavy ? 'weight-2' : 'weight-1';

        const item = document.createElement('div');
        item.className = `sasb-item ${weightClass}`;
        item.textContent = topic;
        
        if (isHeavy) {
            item.title = '權重: 2 (高度相關 - 依據 SASB 準則)';
        } else {
            const hasIndustryColumn = sasbRawData[0] && sasbRawData[0].hasOwnProperty(indName);
            item.title = hasIndustryColumn ? '權重: 1 (一般相關)' : '權重: 未定義 (預設顯示)';
        }

        container.appendChild(item);
    });
}

// 啟動程式
init();