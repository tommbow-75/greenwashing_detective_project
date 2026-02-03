// ============================================
// 🆕 新增:進度追蹤控制器
// ============================================
class RealProgressController {
    constructor() {
        this.container = document.getElementById('progressContainer');
        this.status = document.getElementById('progressStatus');
        this.progressBarFill = document.getElementById('progressBarFill');
        this.progressPercent = document.getElementById('progressPercent');
        this.esgId = null;
        this.pollInterval = null;
        this.smoothInterval = null; // 🆕 新增：用於控制平滑動畫的計時器
        this.pollCount = 0;
        this.maxPollAttempts = 500; // 延長至 25 分鐘 (3s * 500)
        this.isCompleted = false;   // 新增：確保完成後不再執行任何計時邏輯
        this.targetPercent = 0;      // 🆕 實際後端回傳的階段百分比
        this.displayPercent = 0;     // 🆕 目前畫面上顯示的百分比
    }

    show() {
        if (this.container) {
            this.container.style.display = 'block';
            this.reset();
        }
    }

    hide() {
        if (this.container) {
            this.container.style.display = 'none';
            this.stopPolling();
            this.stopSmoothing(); // 🆕 隱藏時停止動畫
        }
    }

    reset() {
        this.pollCount = 0;
        this.isCompleted = false; // 重置狀態
        this.targetPercent = 0;
        this.displayPercent = 0;
        if (this.progressBarFill) this.progressBarFill.style.width = '0%';
        if (this.progressPercent) this.progressPercent.textContent = '0%';
        if (this.status) this.status.textContent = '正在啟動分析流程...';
    }

    startPolling(esgId) {
        this.stopPolling(); // 啟動前先確保舊的已清除
        this.stopSmoothing(); 
        this.esgId = esgId;
        this.show();

        // 初始化目標為 7% (stage1)
        this.targetPercent = 7;
        this.displayPercent = 0;
        this.isCompleted = false;
        this.pollCount = 0;

        // 每 3 秒查詢一次
        this.pollInterval = setInterval(() => {
            this.checkProgress();
        }, 3000);

        this.startSmoothing();
        this.checkProgress();
    }

    stopPolling() {
        if (this.pollInterval) {
            clearInterval(this.pollInterval);
            this.pollInterval = null;
            console.log('⏹️  進度查詢計時器已停止');
        }
    }

    // 🆕 停止平滑動畫
    stopSmoothing() {
        if (this.smoothInterval) {
            clearInterval(this.smoothInterval);
            this.smoothInterval = null;
            console.log('⏹️  進度條動畫計時器已停止');
        }
    }

    // 🆕 平滑動畫引擎核心邏輯
    startSmoothing() {
        this.smoothInterval = setInterval(() => {
            if (this.isCompleted) {
                // 如果已完成，快速衝向 100
                if (this.displayPercent < 100) {
                    // 快速增加以達到 100%
                    this.displayPercent += 1; // 每 100ms 加 1%
                    this.displayPercent = Math.min(this.displayPercent, 100);
                } else {
                    this.displayPercent = 100;
                    this.stopSmoothing();
                    console.log('✅ 進度條動畫已完成');
                }
            } else {
                // 尚未完成時：穩定地每秒增加 0.4% => 每 100ms 增加 0.04%
                if (this.displayPercent < 99) {
                    this.displayPercent += 0.04;
                } else {
                    // 保持在 99% 直到實際完成
                    this.displayPercent = 99;
                }
            }

            // 更新實際 DOM
            this.updateUI(this.displayPercent);
        }, 100); // 100ms 更新一次，視覺上非常流暢
    }


    async checkProgress() {
        // 如果已完成，直接返回，不再執行任何檢查
        if (this.isCompleted) return;
        
        this.pollCount++;

        if (this.pollCount > this.maxPollAttempts) {
            this.stopPolling();
            this.stopSmoothing();
            alert('處理時間過長，請稍後重新搜尋公司代碼查看結果');
            this.hide();
            return;
        }

        try {
            const response = await fetch(`/api/check_progress/${this.esgId}`);
            const data = await response.json();

            console.log("收到進度更新:", data); // 偵錯用

            // 如果後端給的是 analysis_status，這裡就要改寫
            const currentStage = data.stage || data.analysis_status;
            const currentStatus = data.status || (currentStage === 'completed' ? 'completed' : 'processing');

            // 更新進度資訊（包含狀態文字和目標百分比）
            this.updateStageInfo(currentStage, currentStatus);

            // 如果狀態是完成
            if (currentStatus === 'completed') {
                this.isCompleted = true;
                this.targetPercent = 100;
                
                // 立即停止所有計時器，避免用戶被踢出
                this.stopPolling();      // 停止進度查詢
                this.stopSmoothing();    // 停止動畫引擎

                // 強制將進度條設為 100% (確保 UI 顯示一致)
                this.markAllCompleted();

                console.log('✅ 分析完成，所有計時器已停止');

                // 停留1.5秒 再隱藏並顯示結果
                setTimeout(async () => {
                    this.hide(); // 這也會呼叫 stopPolling 和 stopSmoothing，但已經停了所以沒關係

                    // 執行完成後的資料抓取
                    if (this.esgId) {
                        await this.fetchCompletedData(this.esgId);
                    }
                }, 1500);
            }
        } catch (error) {
            console.error('進度查詢錯誤:', error);
        }
    }

    // 🆕 UI 邏輯 - 根據階段更新進度資訊和目標百分比
    updateStageInfo(currentStage, status) {
        // 定義階段對應的百分比（目標值，進度條會漸進式地向此值接近）
        const stageProgressMap = {
            'stage1': 4,  // 下載PDF
            'stage2': 45,  // 平行執行 Word Cloud 和 AI 分析
            'stage3': 58,  // 新聞爬蟲驗證
            'stage4': 85,  // AI 驗證與評分調整
            'stage5': 92,  // 來源可靠度驗證
            'stage6': 97,  // 讀取 P3 JSON 並插入分析結果至資料庫
            'completed': 100
        };

        // 設定目標進度（進度條會漸進式地向此值接近，而不是跳躍）
        this.targetPercent = stageProgressMap[currentStage] || 5;

        // 如果 status 已經是 completed，強迫到 100
        if (status === 'completed') this.targetPercent = 100;

        // 根據不同階段更新狀態文字，會顯示在前端
        const stageMessageMap = {
            'stage1': ' 正在檢索並下載永續報告書',
            'stage2': ' AI 正在分析報告',
            'stage3': ' 正在比對企業的外部新聞',
            'stage4': ' 根據新聞調整漂綠風險評分中',
            'stage5': ' 再次驗證新聞',
            'stage6': ' 即將分析完成...',
            'completed': ' 分析完成！即將顯示結果'
        };

        if (this.status && stageMessageMap[currentStage]) {
            this.status.textContent = stageMessageMap[currentStage];
        }
    }

    // 🆕 更新 UI - 根據當前顯示百分比更新進度條
    updateUI(percent) {
        // 確保百分比在 0-100 之間
        const clampedPercent = Math.min(Math.max(percent, 0), 100);
        
        // 更新進度條寬度
        if (this.progressBarFill) {
            this.progressBarFill.style.width = clampedPercent + '%';
        }
        
        // 更新百分比文字（四捨五入到整數）
        if (this.progressPercent) {
            this.progressPercent.textContent = Math.round(clampedPercent) + '%';
        }
    }

    markAllCompleted() {
        if (this.progressBarFill) this.progressBarFill.style.width = '100%';
        if (this.progressPercent) this.progressPercent.textContent = '100%';
        if (this.status) this.status.textContent = '分析完成！';
    }

    async fetchCompletedData(esgId) {
        const year = esgId.substring(0, 4);
        const companyCode = esgId.substring(4);
        // 呼叫原本的查詢函式，這會觸發 renderCompanies 顯示結果
        await queryCompanyData(parseInt(year), companyCode);
    }
}

// 🆕 初始化進度控制器
const progressController = new RealProgressController();

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

    // ========================================================
    // 🆕 新增: 載入公司清單至下拉選單 (Datalist)
    // ========================================================
    try {
        const response = await fetch('/static/data/companies.json');
        const data = await response.json();

        // 格式化資料給 Tom Select 使用
        const options = data.map(c => ({
            value: c.id,
            text: `${c.id} ${c.name}`
        }));

        // 初始化搜尋框
        new TomSelect("#searchInput", {
            options: options,
            maxItems: 1,
            maxOptions: 50, // 搜尋時最多顯示 50 筆，避免撐開版面
            placeholder: "輸入公司代碼或名稱...",
            create: false,
            // 搜尋邏輯優化
            score: function (search) {
                var score = this.getScoreFunction(search);
                return function (item) {
                    return score(item);
                };
            }
        });
    } catch (err) {
        console.error("載入失敗", err);
    }
    // ========================================================

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

    // 🆕 停止並隱藏進度條（確保任何新搜尋都會清除舊的進度條）
    if (progressController) {
        progressController.stopPolling();
        progressController.hide();
    }

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

        // 獲取風險等級對應的圖片路徑（總風險保持使用圖片）
        const totalImg = getRiskImage(totalRisk.level);

        // E/S/G 使用文字+底色顯示風險等級
        const eRiskLabel = getRiskTextLabel(eLevel.level);
        const sRiskLabel = getRiskTextLabel(sLevel.level);
        const gRiskLabel = getRiskTextLabel(gLevel.level);

        tr.innerHTML = `
            <td style="padding: 1rem; font-weight: bold; color: var(--primary);">${company.name}</td>
            <td style="padding: 1rem;">${company.stockId || '-'}</td>
            <td style="padding: 1rem;">${company.industry}</td>
            <td style="padding: 1rem;">${company.year}</td>
            <td style="padding: 1rem;"><img src="${totalImg}" alt="${totalRisk.text}" style="width: 80px; height: auto; display: block; margin: 0 auto;"></td>
            <td style="padding: 1rem;">${eRiskLabel}</td>
            <td style="padding: 1rem;">${sRiskLabel}</td>
            <td style="padding: 1rem;">${gRiskLabel}</td>
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

// 輔助函式：根據風險等級返回帶底色的文字標籤（用於第二層表格）
// 與 getRiskLabel 類似，但不顯示分數，只顯示風險等級文字
function getRiskTextLabel(level) {
    const riskInfo = {
        'no': '無風險',
        'low': '低風險',
        'medium': '中風險',
        'high': '高風險'
    };

    const text = riskInfo[level] || '未知';
    return `<span class="risk-label ${level}">${text}</span>`;
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
        // 直接使用 adjustment_score 作為最終分數（已經過 AI 計算）
        const netScore = parseFloat(row.adjustment_score) || 0;

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

    // 新結構: 以「產業」為主鍵
    // JSON 結構範例: { "產業": "半導體業", "溫室氣體排放": 2, "空氣品質": 1, ... }
    const industryData = sasbRawData.find(row => row["產業"] === indName);

    // 從該產業物件中找出權重為 2 的所有議題
    const heavyWeightTopics = [];
    if (industryData) {
        for (const [key, value] of Object.entries(industryData)) {
            if (key !== "產業" && value === 2) {
                heavyWeightTopics.push(key);
            }
        }
    }

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
            // 檢查是否找到該產業
            item.title = industryData ? '權重: 1 (一般相關)' : '權重: 未定義 (JSON中無此產業)';
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
    // Note: File name format {year}_{company_code}_wc.json
    const jsonPath = `/word_cloud/wc_output/${year}_${stockId}_wc.json`;
    console.log(`[WordCloud] Attempting to load JSON: ${jsonPath}`, { year, stockId });

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
                <small style="color:#999">(${year}_${stockId}_wc.json)</small>
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

        // 新結構: 以「產業」為主鍵，從第一筆資料的 keys 中提取議題列表
        if (sasbRawData.length > 0) {
            // 取得所有欄位名稱，排除「產業」欄位後即為議題列表
            SASB_TOPICS = Object.keys(sasbRawData[0]).filter(key => key !== "產業");
            console.log("SASB 資料載入成功:", sasbRawData.length, "筆產業資料,", SASB_TOPICS.length, "個議題");
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
}

// --- 自動抓取與分析功能 ---

// 查詢公司資料（呼叫新API）
async function queryCompanyData(year, companyCode) {
    try {
        // 隱藏舊的狀態顯示
        const oldStatusDisplay = document.getElementById('statusDisplay');
        if (oldStatusDisplay) {
            oldStatusDisplay.style.display = 'none';
        }

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

        // ========================================================
        // 🆕 新增：同步 API 資料到全域變數 companiesData
        // ========================================================
        if (result.status === 'completed' && result.data) {
            // 尋找全域變數中是否已經有這一筆 (比對代碼與年度)
            const idx = companiesData.findIndex(c =>
                String(c.stockId) === String(result.data.stockId) &&
                String(c.year) === String(result.data.year)
            );

            if (idx !== -1) {
                // 找到舊資料，用 API 回傳的「完整最新資料」覆蓋它
                companiesData[idx] = result.data;
                console.log("✅ 全域變數已更新最新分析結果");
            } else {
                // 如果原本不在清單中，就推入新資料
                companiesData.push(result.data);
                console.log("✅ 已新增一筆分析資料到全域變數");
            }
        }
        // ========================================================

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

        // 🆕 停止進度條輪詢並隱藏進度條
        if (progressController) {
            progressController.stopPolling();
            progressController.hide();
        }

        // 使用現有的 renderCompanies 函式顯示資料
        filteredData = [data];
        currentPage = 1;
        renderCompanies(filteredData);

    } else if (status === 'processing') {
        // ⏳ 處理中 - 自動恢復進度追蹤（支援頁面重新整理後恢復顯示）
        statusDisplay.style.display = 'none';
        resultsDashboard.style.display = 'none';

        // 🆕 如果有 esg_id，自動啟動進度追蹤
        if (year && companyCode) {
            const esgId = `${year}${companyCode}`;
            console.log(`🔄 偵測到分析進行中，自動恢復進度追蹤: ${esgId}`);
            progressController.startPolling(esgId);
        }

    } else if (status === 'resume_needed') {
        // 🆕 需要恢復 - 顯示斷點恢復選項
        statusDisplay.style.display = 'block';
        resultsDashboard.style.display = 'none';

        statusContent.innerHTML = `
            <div style="text-align: center; padding: 2rem; background: #fff3cd; border-radius: 8px;">
                <h3 style="color: #856404;">⚠️ ${message}</h3>
                <p style="color: #856404; margin: 1rem 0;">您可以選擇從斷點繼續，或重新開始分析。</p>
                <button class="btn" onclick="confirmAutoFetch(${year}, '${companyCode}')" style="margin-top: 1rem; background: var(--primary); color: white;">
                    ▶️ 從斷點繼續
                </button>
            </div>
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
        // 不再使用舊的 processing 狀態，直接啟動進度條
        const esgId = `${year}${companyCode}`;

        // 1. 隱藏其他狀態框
        document.getElementById('statusDisplay').style.display = 'none';

        // 2. 啟動進度控制器
        progressController.startPolling(esgId);

        // 3. 呼叫後端 API 啟動非同步處理
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