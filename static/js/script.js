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

    // 3. 創建動態驗證 tooltip
    createVerifiedTooltip();

    // 4. (選擇性) 如果想要一進來就顯示列表，可以打開下面這行
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

    // 隱藏狀態顯示區域（清除之前的錯誤或成功訊息）
    document.getElementById('statusDisplay').style.display = 'none';

    // 取得輸入的公司代碼和年份
    const companyCode = document.getElementById('searchInput').value.trim();
    const year = document.getElementById('yearFilter').value;

    // 如果有輸入公司代碼，則呼叫新的查詢 API
    if (companyCode && year) {
        queryCompanyData(parseInt(year), companyCode);
    } else {
        // 否則使用舊的篩選邏輯
        filterCompanies();

        // 隱藏初始提示，顯示結果
        document.getElementById('initialPrompt').style.display = 'none';
        document.getElementById('resultsDashboard').style.display = 'block';
    }
}

function filterCompanies() {
    const search = document.getElementById('searchInput').value.toUpperCase().trim();
    const industry = document.getElementById('industryFilter').value;
    const year = document.getElementById('yearFilter').value;

    console.log("Filtering:", { search, industry, year });

    // 使用全域的 companiesData (來自 HTML)
    filteredData = companiesData.filter(c => {
        // 只比對公司代碼（stockId）
        const matchSearch = !search || (c.stockId && c.stockId.includes(search));
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

        // 獲取風險等級對應的圖片路徑
        const totalImg = getRiskImage(totalRisk.level);
        const eImg = getRiskImage(eLevel.level);
        const sImg = getRiskImage(sLevel.level);
        const gImg = getRiskImage(gLevel.level);

        tr.innerHTML = `
            <td style="padding: 1rem; font-weight: bold; color: var(--primary);">${company.name}</td>
            <td style="padding: 1rem;">${company.stockId || '-'}</td>
            <td style="padding: 1rem;">${company.industry}</td>
            <td style="padding: 1rem;">${company.year}</td>
            <td style="padding: 1rem;"><img src="${totalImg}" alt="${totalRisk.text}" style="width: 80px; height: auto; display: block; margin: 0 auto;"></td>
            <td style="padding: 1rem;"><img src="${eImg}" alt="${eLevel.text}" style="width: 80px; height: auto; display: block; margin: 0 auto;"></td>
            <td style="padding: 1rem;"><img src="${sImg}" alt="${sLevel.text}" style="width: 80px; height: auto; display: block; margin: 0 auto;"></td>
            <td style="padding: 1rem;"><img src="${gImg}" alt="${gLevel.text}" style="width: 80px; height: auto; display: block; margin: 0 auto;"></td>
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
    // 假設: 0-39 高風險(紅), 40-59 中風險(橘紅), 60-84 低風險(金黃), >84 無風險(綠)
    if (num <= 39) return { text: '高', color: 'red', level: 'high' };
    if (num <= 59) return { text: '中', color: '#FF6B35', level: 'medium' };  // 更明顯的橘紅色
    if (num <= 84) return { text: '低', color: '#FFC107', level: 'low' };  // 更明亮的金黃色
    return { text: '無', color: 'green', level: 'no' };
};

// 輔助函式：根據風險等級返回圖片路徑
function getRiskImage(level) {
    const basePath = '/static/images/';
    return `${basePath}${level}_risk.png`;
}

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

    company.layer4Data.forEach((row, index) => {
        // 1. 計算調整後的分數 (Net Score)
        const initialRisk = parseFloat(row.risk_score) || 0;
        // const deduction = parseFloat(row.adjustment_score) || 0;
        // 分數最低扣到 0，不出現負分
        // const netScore = Math.max(0, initialRisk - deduction).toFixed(1);

        const tr = document.createElement('tr');
        tr.style.cursor = 'pointer';
        tr.style.transition = 'background-color 0.2s';
        const expandId = `layer4-expand-${index}`;

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

        // Hover 效果
        tr.addEventListener('mouseenter', function () {
            this.style.backgroundColor = '#f8f9fa';
        });
        tr.addEventListener('mouseleave', function () {
            this.style.backgroundColor = '';
        });

        // 整行點擊展開
        tr.addEventListener('click', function () {
            toggleExpandRow(expandId, {
                type: 'layer4',
                sasbTopic: row.SASB_topic || '-',
                reportClaim: row.report_claim || '-',
                greenwashingFactor: row.greenwashing_factor || '-'
            }, tr);
        });

        tableBody.appendChild(tr);
    });
}

// [Layer 5] 外部新聞揭露對比
function renderLayer5(company) {
    const tableBody = document.getElementById('layer5Table');
    tableBody.innerHTML = '';

    const dataWithEvidence = company.layer4Data;

    if (!dataWithEvidence || dataWithEvidence.length === 0) {
        tableBody.innerHTML = '<tr><td colspan="6" style="text-align:center;">無相關外部證據資料</td></tr>';
        return;
    }

    dataWithEvidence.forEach((row, index) => {
        // 計算 Net Score
        const initialRisk = parseFloat(row.risk_score) || 0;
        const deduction = parseFloat(row.adjustment_score) || 0;
        const netScore = Math.max(0, initialRisk - deduction).toFixed(1);

        const evidenceText = row.external_evidence || '-';
        const evidenceUrl = row.external_evidence_url;
        const isVerified = row.is_verified === true || row.is_verified === 1; // 支援 boolean 或 int

        // 驗證徽章 (綠色圓形勾勾)
        const verifiedBadge = isVerified
            ? '<span class="verified-badge" style="display:inline-block; width:16px; height:16px; background:#4CAF50; border-radius:50%; color:white; text-align:center; line-height:16px; font-size:12px; margin-right:4px;">✓</span>'
            : '';

        // 如果有 URL，將證據文字變成超連結（已驗證時，整個區域都能觸發懸停提示）
        let evidenceDisplay;
        if (evidenceUrl) {
            const verifiedClass = isVerified ? ' verified-evidence' : '';
            evidenceDisplay = `<a href="${evidenceUrl}" target="_blank" onclick="event.stopPropagation();" class="evidence-link${verifiedClass}" style="color: var(--primary); text-decoration: underline; position: relative;">${verifiedBadge}${cutString(evidenceText, 15)}</a>`;
        } else {
            const verifiedClass = isVerified ? ' verified-evidence' : '';
            evidenceDisplay = `<span class="evidence-text${verifiedClass}" style="position: relative;">${verifiedBadge}${cutString(evidenceText, 15)}</span>`;
        }

        const status = row.consistency_status || '待確認';
        const msci = row.MSCI_flag || '-';

        let statusColor = 'black';
        if (status.includes('不一致')) statusColor = 'var(--danger)';
        else if (status.includes('一致')) statusColor = 'var(--success)';

        const tr = document.createElement('tr');
        tr.style.cursor = 'pointer';
        tr.style.transition = 'background-color 0.2s';
        const expandId = `layer5-expand-${index}`;

        tr.innerHTML = `
            <td>${row.ESG_category}</td>
            <td title="${row.report_claim}">${cutString(row.report_claim, 15)}</td>
            <td class="evidence-cell">${evidenceDisplay}</td>
            <td style="color:${statusColor}; font-weight:bold;">${status}</td>
            <td>${msci}</td>
            <td>${getRiskLabel(netScore)}</td>
        `;

        // Hover 效果
        tr.addEventListener('mouseenter', function () {
            this.style.backgroundColor = '#f8f9fa';
        });
        tr.addEventListener('mouseleave', function () {
            this.style.backgroundColor = '';
        });

        // 整行點擊展開
        tr.addEventListener('click', function (e) {
            // 如果點擊的是連結，不觸發展開
            if (e.target.tagName === 'A') return;

            toggleExpandRow(expandId, {
                type: 'layer5',
                reportClaim: row.report_claim || '-',
                externalEvidence: evidenceText
            }, tr);
        });

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
                    show: false
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

// 切換展開行顯示
function toggleExpandRow(expandId, data, parentRow) {
    const existingExpandRow = document.getElementById(expandId);

    if (existingExpandRow) {
        // 已存在，則移除（收縮動畫）
        const contentDiv = existingExpandRow.querySelector('td > div');

        // 添加收縮動畫
        existingExpandRow.style.opacity = '0';
        if (contentDiv) {
            contentDiv.style.transform = 'translateY(-10px)';
        }

        // 動畫結束後移除元素
        setTimeout(() => {
            existingExpandRow.remove();
        }, 300);
    } else {
        // 不存在，則創建展開行
        const expandRow = document.createElement('tr');
        expandRow.id = expandId;
        expandRow.style.backgroundColor = '#f8fbff';
        expandRow.style.opacity = '0';
        expandRow.style.transition = 'opacity 0.3s ease-out';

        const colCount = parentRow.cells.length;

        let content = '';

        if (data.type === 'layer4') {
            // 第四層：顯示 sasb_topic、report_claim、greenwashing_factor
            content = `
                <div style="padding: 1.5rem; line-height: 1.8; color: #333; transform: translateY(-10px); transition: transform 0.5s ease-out;">
                    <div style="display: grid; gap: 1rem;">
                        <div style="background: white; padding: 1rem; border-radius: 8px; border-left: 4px solid #4CAF50;">
                            <div style="font-weight: bold; color: #2c3e50; margin-bottom: 0.5rem; font-size: 0.9em;">
                                📊 SASB 議題
                            </div>
                            <div style="color: #34495e;">
                                ${data.sasbTopic}
                            </div>
                        </div>
                        
                        <div style="background: white; padding: 1rem; border-radius: 8px; border-left: 4px solid #2196F3;">
                            <div style="font-weight: bold; color: #2c3e50; margin-bottom: 0.5rem; font-size: 0.9em;">
                                📝 ESG 報告宣稱
                            </div>
                            <div style="color: #34495e; white-space: pre-wrap; word-wrap: break-word;">
                                ${data.reportClaim}
                            </div>
                        </div>
                        
                        <div style="background: white; padding: 1rem; border-radius: 8px; border-left: 4px solid #FF9800;">
                            <div style="font-weight: bold; color: #2c3e50; margin-bottom: 0.5rem; font-size: 0.9em;">
                                ⚠️ 漂綠因子
                            </div>
                            <div style="color: #34495e;">
                                ${data.greenwashingFactor}
                            </div>
                        </div>
                    </div>
                </div>
            `;
        } else if (data.type === 'layer5') {
            // 第五層：顯示 report_claim、external_evidence
            content = `
                <div style="padding: 1.5rem; line-height: 1.8; color: #333; transform: translateY(-10px); transition: transform 0.5s ease-out;">
                    <div style="display: grid; gap: 1rem;">
                        <div style="background: white; padding: 1rem; border-radius: 8px; border-left: 4px solid #2196F3;">
                            <div style="font-weight: bold; color: #2c3e50; margin-bottom: 0.5rem; font-size: 0.9em;">
                                📝 ESG 報告宣稱
                            </div>
                            <div style="color: #34495e; white-space: pre-wrap; word-wrap: break-word;">
                                ${data.reportClaim}
                            </div>
                        </div>
                        
                        <div style="background: white; padding: 1rem; border-radius: 8px; border-left: 4px solid #9C27B0;">
                            <div style="font-weight: bold; color: #2c3e50; margin-bottom: 0.5rem; font-size: 0.9em;">
                                🔍 外部證據
                            </div>
                            <div style="color: #34495e; white-space: pre-wrap; word-wrap: break-word;">
                                ${data.externalEvidence}
                            </div>
                        </div>
                    </div>
                </div>
            `;
        }

        expandRow.innerHTML = `
            <td colspan="${colCount}" style="padding: 0; border-left: 3px solid var(--primary);">
                ${content}
            </td>
        `;

        // 在當前行後插入展開行
        parentRow.parentNode.insertBefore(expandRow, parentRow.nextSibling);

        // 觸發展開動畫（使用 requestAnimationFrame 確保 DOM 更新後才開始動畫）
        requestAnimationFrame(() => {
            expandRow.style.opacity = '1';
            const contentDiv = expandRow.querySelector('td > div');
            if (contentDiv) {
                contentDiv.style.transform = 'translateY(0)';
            }
        });
    }
}

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


// --- 動態驗證 Tooltip 功能 ---
function createVerifiedTooltip() {
    // 創建 tooltip 元素
    const tooltip = document.createElement('div');
    tooltip.id = 'verified-tooltip';
    tooltip.textContent = '已驗證';
    document.body.appendChild(tooltip);

    // 追蹤滑鼠位置
    let mouseX = 0;
    let mouseY = 0;

    document.addEventListener('mousemove', (e) => {
        mouseX = e.clientX;
        mouseY = e.clientY;

        // 如果 tooltip 是顯示狀態，更新位置
        if (tooltip.style.display === 'block') {
            tooltip.style.left = (mouseX + 15) + 'px';
            tooltip.style.top = (mouseY + 15) + 'px';
        }
    });

    // 使用事件委派處理所有的 verified-badge 和 verified-evidence
    document.addEventListener('mouseover', (e) => {
        if (e.target.classList.contains('verified-badge') ||
            e.target.classList.contains('verified-evidence') ||
            e.target.closest('.verified-evidence')) {
            tooltip.style.display = 'block';
            tooltip.style.left = (mouseX + 15) + 'px';
            tooltip.style.top = (mouseY + 15) + 'px';
        }
    });

    document.addEventListener('mouseout', (e) => {
        if (e.target.classList.contains('verified-badge') ||
            e.target.classList.contains('verified-evidence') ||
            e.target.closest('.verified-evidence')) {
            tooltip.style.display = 'none';
        }
    });

// --- 自動抓取與分析功能 ---

// 查詢公司資料（呼叫新API）
async function queryCompanyData(year, companyCode) {
    try {
        // 先顯示載入中狀態/或重置狀態，避免舊錯誤訊息殘留
        showAnalysisStatus('processing', '查詢資料中...');

        const response = await fetch('/api/query_company', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                year: year,
                company_code: companyCode,
                auto_fetch: false  // 先不自動抓取，等用戶確認
            })
        });

        // 檢查回應是否成功
        if (!response.ok) {
            // 嘗試解析 JSON 錯誤訊息
            const contentType = response.headers.get("content-type");
            if (contentType && contentType.indexOf("application/json") !== -1) {
                const errData = await response.json();
                throw new Error(errData.message || `伺服器錯誤: ${response.status}`);
            } else {
                // 如果回傳的不是 JSON (例如 HTML 錯誤頁面)
                const text = await response.text();
                console.error("非 JSON 回應:", text.substring(0, 200)); // 只印出前200字避免洗版
                throw new Error(`伺服器回應異常 (${response.status})，請稍後再試`);
            }
        }

        const result = await response.json();
        console.log('Query result:', result);

        // 隱藏初始提示
        document.getElementById('initialPrompt').style.display = 'none';

        // 根據不同狀態顯示結果
        showAnalysisStatus(result.status, result.message, result.data, year, companyCode);

    } catch (error) {
        console.error('查詢錯誤:', error);
        // 處理 JSON 解析錯誤 (Unexpected token <)
        let msg = error.message;
        if (msg.includes("Unexpected token") || msg.includes("JSON")) {
            msg = "系統錯誤 (解析失敗)，可能伺服器發生異常";
        }
        showAnalysisStatus('error', msg);
    }
}

// 顯示不同狀態的內容
function showAnalysisStatus(status, message, data = null, year = null, companyCode = null) {
    const statusDisplay = document.getElementById('statusDisplay');
    const statusContent = document.getElementById('statusContent');
    const resultsDashboard = document.getElementById('resultsDashboard');

    // 清空舊內容
    statusContent.innerHTML = '';

    if (status === 'completed') {
        // ✅ 已完成：顯示資料
        statusDisplay.style.display = 'none';
        resultsDashboard.style.display = 'block';

        // 使用現有的 renderCompanies 函式顯示資料
        filteredData = [data];
        currentPage = 1;
        renderCompanies(filteredData);

    } else if (status === 'processing') {
        // ⏳ 處理中
        statusDisplay.style.display = 'block';
        resultsDashboard.style.display = 'none';

        statusContent.innerHTML = `
            <div style="text-align: center; padding: 2rem;">
                <div class="spinner" style="border: 4px solid #f3f3f3; border-top: 4px solid var(--primary); border-radius: 50%; width: 40px; height: 40px; animation: spin 1s linear infinite; margin: 0 auto 1rem;"></div>
                <h3 style="color: var(--primary);">⏳ ${message}</h3>
                <p style="color: var(--text-secondary);">系統正在進行分析，這可能需要數分鐘...</p>
            </div>
            <style>
                @keyframes spin {
                    0% { transform: rotate(0deg); }
                    100% { transform: rotate(360deg); }
                }
            </style>
        `;

    } else if (status === 'failed') {
        // ❌ 失敗
        statusDisplay.style.display = 'block';
        resultsDashboard.style.display = 'none';

        statusContent.innerHTML = `
            <div style="text-align: center; padding: 2rem; background: #fff3cd; border-radius: 8px;">
                <h3 style="color: #856404;">❌ 分析失敗</h3>
                <p style="color: #856404;">${message}</p>
                <button class="btn" onclick="confirmAutoFetch(${year}, '${companyCode}')" style="margin-top: 1rem;">
                    🔄 重新啟動分析
                </button>
            </div>
        `;

    } else if (status === 'validation_needed') {
        // ❓ 需要確認
        statusDisplay.style.display = 'block';
        resultsDashboard.style.display = 'none';

        statusContent.innerHTML = `
            <div style="text-align: center; padding: 2rem; background: #d1ecf1; border-radius: 8px;">
                <h3 style="color: #0c5460;">❓ ${message}</h3>
                <p style="color: #0c5460; margin: 1rem 0;">此操作將自動下載永續報告書並進行 AI 分析，可能需要較長時間。</p>
                <button class="btn" onclick="confirmAutoFetch(${year}, '${companyCode}')" style="margin-top: 1rem; background: var(--primary); color: white;">
                    ✅ 確認啟動
                </button>
                <button class="btn" onclick="cancelAutoFetch()" style="margin-top: 1rem; margin-left: 1rem; background: #6c757d; color: white;">
                    ❌ 取消
                </button>
            </div>
        `;

    } else if (status === 'not_found') {
        // ❌ 查無報告
        statusDisplay.style.display = 'block';
        resultsDashboard.style.display = 'none';

        statusContent.innerHTML = `
            <div style="text-align: center; padding: 2rem; background: #f8d7da; border-radius: 8px;">
                <h3 style="color: #721c24;">❌ ${message}</h3>
                <p style="color: #721c24;">請確認公司代碼與年度是否正確。</p>
            </div>
        `;

    } else {
        // 🔴 錯誤
        statusDisplay.style.display = 'block';
        resultsDashboard.style.display = 'none';

        statusContent.innerHTML = `
            <div style="text-align: center; padding: 2rem; background: #f8d7da; border-radius: 8px;">
                <h3 style="color: #721c24;">🔴 ${message}</h3>
            </div>
        `;
    }
}

// 確認啟動自動抓取
async function confirmAutoFetch(year, companyCode) {
    try {
        // 顯示處理中狀態
        showAnalysisStatus('processing', '正在啟動自動抓取與分析...');

        const response = await fetch('/api/query_company', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                year: year,
                company_code: companyCode,
                auto_fetch: true  // 同意自動抓取
            })
        });

        const result = await response.json();
        console.log('Auto-fetch result:', result);

        // 顯示最終結果
        showAnalysisStatus(result.status, result.message, result.data, year, companyCode);

    } catch (error) {
        console.error('自動抓取錯誤:', error);
        showAnalysisStatus('error', `系統錯誤: ${error.message}`);
    }
}

// 取消自動抓取
function cancelAutoFetch() {
    document.getElementById('statusDisplay').style.display = 'none';
    document.getElementById('initialPrompt').style.display = 'block';
}