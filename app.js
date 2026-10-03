const $=s=>document.querySelector(s);
const esc=s=>String(s??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
let T={},lang=localStorage.lang||"uz",cur=+localStorage.co||0,cos=[],editId=null,TY={types:{},cats:{}};
let filterFromMonth="", filterToMonth="";

const co=()=>cos.find(c=>c.id===cur)||{};
const catLabel=k=>TY.cats[k]?.[lang]||k||"—";
const catMeta=k=>TY.cats[k]||{pnl_group:null,cf_activity:"operating",balance_group:null};

function showToast(msg) {
  const t = document.createElement("div");
  t.className = "toast-notify";
  t.textContent = msg;
  document.body.appendChild(t);
  setTimeout(() => t.remove(), 3500);
}

function fillCats(f,val){
  const y=TY.types[co().type]||TY.types.other, list=y[f.type.value];
  f.category.innerHTML=list.map(k=>`<option value="${k}">${esc(catLabel(k))}</option>`).join("")+`<option value="__other">${t("otherCat")}</option>`;
  const known=list.includes(val);
  f.category.value=known?val:(val?"__other":list[0]);
  f.custom.hidden=f.category.value!=="__other";
  f.custom.value=known?"":(val?catLabel(val):"");
}

const t=k=>T[k]||k;
const fmt=n=>new Intl.NumberFormat(lang==="en"?"en-US":lang==="ru"?"ru-RU":"uz-UZ",{maximumFractionDigits:2}).format(n);
const api=(u,m="GET",b)=>fetch("/api/"+u,{method:m,headers:{"Content-Type":"application/json"},body:b&&JSON.stringify(b)}).then(r=>r.json());

async function setLang(l){
  lang=l;localStorage.lang=l;document.documentElement.lang=l;
  T=await (await fetch(`/static/i18n/${l}.json`)).json();
  $("#lang").value=l;
  document.querySelectorAll("[data-t]").forEach(e=>e.textContent=t(e.dataset.t));
  document.title=t("title");
  render();
}

async function load(){
  cos=await api("companies");
  if(!cos.find(c=>c.id===cur))cur=cos[0]?.id||0;
  localStorage.co=cur;
  filterFromMonth="";
  filterToMonth="";
  $("#co").innerHTML=cos.map(c=>`<option value="${c.id}"${c.id===cur?" selected":""}>${esc(c.name)}</option>`).join("");
  render();
  if(!cos.length)openCo();
}

async function openDrillDown(accountKey, labelName, month="") {
  const dlg = $("#drill-dlg");
  const query = `company=${cur}&account=${encodeURIComponent(accountKey)}&from_month=${encodeURIComponent(filterFromMonth)}&to_month=${encodeURIComponent(filterToMonth)}${month?`&month=${encodeURIComponent(month)}`:''}`;
  const txList = await api("account_tx?" + query);

  dlg.innerHTML = `
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;">
      <h2 style="margin:0;font-size:20px;">${t("accountTxDetail")}: <span style="color:var(--primary);">${esc(labelName)}</span> ${month?`(${month})`:''}</h2>
      <button class="md-btn md-btn-outlined" id="close-drill">${t("close")}</button>
    </div>
    ${txList.length ? `
      <div class="wrap">
        <table>
          <thead>
            <tr><th>${t("date")}</th><th>${t("type")}</th><th>${t("category")}</th><th class="n">${t("amount")}</th><th>${t("note")}</th><th class="acts">${t("actions")}</th></tr>
          </thead>
          <tbody>
            ${txList.map(x=>`
              <tr>
                <td>${x.date}</td>
                <td class="${x.type==="income"?"in":"out"}">${t(x.type)}</td>
                <td>${esc(catLabel(x.category))}</td>
                <td class="n">${fmt(x.amount)}</td>
                <td>${esc(x.note)}</td>
                <td class="acts">
                  <button class="link" data-e="${x.id}">${t("edit")}</button>
                  <button class="link" data-d="${x.id}">${t("delete")}</button>
                </td>
              </tr>
            `).join("")}
          </tbody>
        </table>
      </div>
    ` : `<p class="empty">${t("noTxFound")}</p>`}
  `;

  $("#close-drill").onclick = () => dlg.close();

  dlg.onclick = async e => {
    const d = e.target.dataset;
    if (d.d && confirm(t("confirm"))) {
      await api("tx/" + d.d, "DELETE");
      dlg.close();
      render();
    }
    if (d.e) {
      const x = txList.find(v => v.id == d.e);
      editId = x.id;
      dlg.close();
      const f = $("#f");
      for (const k of ["date", "type", "amount", "note"]) f[k].value = x[k];
      fillCats(f, x.category);
      f.amount.focus();
    }
  };

  dlg.showModal();
}

function openAIDialog() {
  const dlg = $("#ai-dlg");
  let parsedData = null;
  let selectedFile = null;

  dlg.innerHTML = `
    <div class="ai-modal-header">
      <h2><span class="material-symbols-outlined">auto_awesome</span> ${t("aiAssistant")}</h2>
      <button class="md-btn md-btn-outlined" id="close-ai">${t("close")}</button>
    </div>
    
    <label style="margin-bottom:6px;">${t("aiPromptPlaceholder")}</label>
    <textarea id="ai-input" class="ai-prompt-area" placeholder="${t("aiPromptPlaceholder")}"></textarea>

    <!-- File and Picture Upload Dropzone -->
    <div id="ai-dropzone" class="ai-dropzone">
      <input type="file" id="ai-file-input" accept="image/*,.pdf,.txt,.csv,.tsv,.json,.md,.xlsx,.xls,.log" hidden>
      <div class="ai-dropzone-content">
        <span class="material-symbols-outlined ai-dropzone-icon">upload_file</span>
        <span class="ai-dropzone-title">${t("uploadFileOrPic")}</span>
        <span class="ai-dropzone-sub">${t("dragDropHint")}</span>
      </div>
    </div>

    <!-- Selected File Preview Container -->
    <div id="ai-file-preview-wrap" hidden></div>

    <div style="margin-top:14px; display:flex; gap:10px; align-items:center;">
      <button id="btn-analyze-ai" class="md-btn md-btn-ai">
        <span class="material-symbols-outlined">auto_awesome</span> ${t("analyzeWithAI")}
      </button>
    </div>

    <div id="ai-preview" class="ai-preview-box" hidden></div>
  `;

  const dropzone = $("#ai-dropzone");
  const fileInput = $("#ai-file-input");
  const previewWrap = $("#ai-file-preview-wrap");

  dropzone.onclick = () => fileInput.click();

  dropzone.ondragover = e => { e.preventDefault(); dropzone.classList.add("dragover"); };
  dropzone.ondragleave = e => { e.preventDefault(); dropzone.classList.remove("dragover"); };
  dropzone.ondrop = e => {
    e.preventDefault();
    dropzone.classList.remove("dragover");
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFileSelected(e.dataTransfer.files[0]);
    }
  };

  fileInput.onchange = () => {
    if (fileInput.files && fileInput.files[0]) {
      handleFileSelected(fileInput.files[0]);
    }
  };

  function handleFileSelected(file) {
    selectedFile = file;
    const isImage = file.type.startsWith("image/");
    const sizeKb = (file.size / 1024).toFixed(1);

    previewWrap.hidden = false;
    previewWrap.innerHTML = `
      <div class="ai-file-preview">
        <div class="ai-file-preview-left">
          ${isImage ? `<img id="ai-img-thumb-preview" class="ai-img-thumb" src="" alt="preview">` : `<span class="material-symbols-outlined ai-doc-icon">description</span>`}
          <div class="ai-file-info">
            <span class="ai-file-name">${esc(file.name)}</span>
            <span class="ai-file-size">${sizeKb} KB • ${t("fileAttached")}</span>
          </div>
        </div>
        <button id="btn-remove-file" class="btn-remove-file" title="${t("removeFile")}">
          <span class="material-symbols-outlined">close</span>
        </button>
      </div>
    `;

    if (isImage) {
      const reader = new FileReader();
      reader.onload = e => {
        const imgEl = $("#ai-img-thumb-preview");
        if (imgEl) imgEl.src = e.target.result;
      };
      reader.readAsDataURL(file);
    }

    $("#btn-remove-file").onclick = () => {
      selectedFile = null;
      fileInput.value = "";
      previewWrap.hidden = true;
      previewWrap.innerHTML = "";
    };
  }

  $("#close-ai").onclick = () => dlg.close();

  $("#btn-analyze-ai").onclick = async () => {
    const text = $("#ai-input").value.trim();
    if (!text && !selectedFile) {
      alert("Please enter text prompt or attach a file/picture.");
      return;
    }
    
    const btn = $("#btn-analyze-ai");
    btn.disabled = true;
    btn.textContent = t("processingFile");

    try {
      if (selectedFile) {
        const fd = new FormData();
        fd.append("file", selectedFile);
        fd.append("text", text);
        fd.append("company_id", cur);

        const res = await fetch("/api/ai_parse_file", {
          method: "POST",
          body: fd
        });
        parsedData = await res.json();
      } else {
        parsedData = await api("ai_parse", "POST", { text, company_id: cur });
      }
      renderAIPreview(parsedData);
    } catch(err) {
      alert("AI File Analysis Error: " + (err.message || err));
    } finally {
      btn.disabled = false;
      btn.innerHTML = `<span class="material-symbols-outlined">auto_awesome</span> ${t("analyzeWithAI")}`;
    }
  };

  function renderAIPreview(data) {
    const box = $("#ai-preview");
    box.hidden = false;
    
    const bal = data.balances || {};
    const txs = data.transactions || [];

    const balHtml = anyDefined(bal) ? `
      <h4>${t("opening")} (${t("aiResultsSummary")})</h4>
      <div class="ai-balances-grid">
        ${bal.opening_cash != null ? `<div class="ai-bal-card"><small>${t("openingCash")}</small><strong>${fmt(bal.opening_cash)}</strong></div>` : ''}
        ${bal.opening_fixed_assets != null ? `<div class="ai-bal-card"><small>${t("openingFixedAssets")}</small><strong>${fmt(bal.opening_fixed_assets)}</strong></div>` : ''}
        ${bal.opening_loans != null ? `<div class="ai-bal-card"><small>${t("openingLoans")}</small><strong>${fmt(bal.opening_loans)}</strong></div>` : ''}
        ${bal.opening_equity != null ? `<div class="ai-bal-card"><small>${t("openingEquity")}</small><strong>${fmt(bal.opening_equity)}</strong></div>` : ''}
        ${bal.share_count != null ? `<div class="ai-bal-card"><small>${t("shareCount")}</small><strong>${fmt(bal.share_count)}</strong></div>` : ''}
      </div>
    ` : '';

    const txHtml = txs.length ? `
      <h4>${t("transactions")} (${txs.length})</h4>
      <div class="wrap" style="max-height:220px;">
        <table>
          <thead>
            <tr><th>${t("date")}</th><th>${t("type")}</th><th>${t("category")}</th><th class="n">${t("amount")}</th><th>${t("note")}</th></tr>
          </thead>
          <tbody>
            ${txs.map(x=>`
              <tr>
                <td>${x.date}</td>
                <td class="${x.type==="income"?"in":"out"}">${t(x.type)}</td>
                <td>${esc(catLabel(x.category))}</td>
                <td class="n">${fmt(x.amount)}</td>
                <td>${esc(x.note)}</td>
              </tr>
            `).join("")}
          </tbody>
        </table>
      </div>
    ` : '';

    box.innerHTML = `
      <p style="margin:0 0 12px;font-weight:600;color:var(--primary);">${esc(data.summary)}</p>
      ${balHtml}
      ${txHtml}
      <div style="margin-top:16px;">
        <button id="btn-apply-ai" class="md-btn md-btn-primary">
          <span class="material-symbols-outlined">check_circle</span> ${t("applyAIToSystem")}
        </button>
      </div>
    `;

    $("#btn-apply-ai").onclick = async () => {
      $("#btn-apply-ai").disabled = true;
      const res = await api("ai_apply", "POST", {
        company_id: cur,
        balances: data.balances,
        transactions: data.transactions
      });
      if (res.ok) {
        dlg.close();
        showToast(t("aiSuccessToast"));
        render();
      }
    };
  }

  function anyDefined(obj) {
    return Object.values(obj).some(v => v !== None && v !== null);
  }

  dlg.showModal();
}

async function render(){
  const app=$("#app");
  if(!cur){
    app.innerHTML=`<p class="empty">${t("noCompany")}</p><button class="md-btn md-btn-primary" onclick="openCo()">${t("newCompany")}</button>`;
    return;
  }

  const query=`company=${cur}&from_month=${encodeURIComponent(filterFromMonth)}&to_month=${encodeURIComponent(filterToMonth)}`;
  const [r,tx]=await Promise.all([api("report?"+query),api("tx?company="+cur)]);
  const max=Math.max(1,...r.categories.map(c=>c.total));

  if(!filterFromMonth) filterFromMonth = r.start_month;
  if(!filterToMonth) filterToMonth = r.end_month;

  const mList = r.months_list || [];

  const renderPnlRow = (labelKey, metricKey, isBold=false, cssClass="") => {
    const cellsHtml = mList.map(m => {
      const val = r.monthly_pnl[m] ? r.monthly_pnl[m][metricKey] : 0;
      return `<td class="n ${cssClass}">${fmt(val)}</td>`;
    }).join("");
    const totalVal = r.monthly_pnl.total ? r.monthly_pnl.total[metricKey] : 0;
    const tag = isBold ? "strong" : "span";
    return `<tr class="clickable-row ${isBold?'subtotal':''}" title="${t('clickToViewTx')}" data-acc="${metricKey}">
      <td><${tag}>${t(labelKey)}</${tag}></td>
      ${cellsHtml}
      <td class="n ${cssClass}"><${tag}>${fmt(totalVal)}</${tag}></td>
    </tr>`;
  };

  const renderBSRow = (labelKey, getValFn, metricKey, isBold=false, cssClass="") => {
    const cellsHtml = mList.map(m => {
      const val = r.monthly_balance_sheet[m] ? getValFn(r.monthly_balance_sheet[m]) : 0;
      return `<td class="n ${cssClass}">${fmt(val)}</td>`;
    }).join("");
    const latestVal = r.monthly_balance_sheet.total ? getValFn(r.monthly_balance_sheet.total) : 0;
    const tag = isBold ? "strong" : "span";
    return `<tr class="clickable-row ${isBold?'subtotal':''}" title="${t('clickToViewTx')}" data-acc="${metricKey}">
      <td><${tag}>${t(labelKey)}</${tag}></td>
      ${cellsHtml}
      <td class="n ${cssClass}"><${tag}>${fmt(latestVal)}</${tag}></td>
    </tr>`;
  };

  const renderCfRow = (labelKey, metricKey, isBold=false, cssClass="") => {
    const cellsHtml = mList.map(m => {
      const val = r.monthly_cash_flow[m] ? r.monthly_cash_flow[m][metricKey] : 0;
      return `<td class="n ${cssClass}">${fmt(val)}</td>`;
    }).join("");
    const totalVal = r.monthly_cash_flow.total ? r.monthly_cash_flow.total[metricKey] : 0;
    const tag = isBold ? "strong" : "span";
    return `<tr class="clickable-row ${isBold?'subtotal':''}" title="${t('clickToViewTx')}" data-acc="${metricKey}">
      <td><${tag}>${t(labelKey)}</${tag}></td>
      ${cellsHtml}
      <td class="n ${cssClass}"><${tag}>${fmt(totalVal)}</${tag}></td>
    </tr>`;
  };

  app.innerHTML=`
  <div class="balance"><small>${t("balance")}</small><strong>${fmt(r.balance)}</strong></div>
  
  <div class="stats">
    <div>${t("opening")}<br><strong>${fmt(r.opening)}</strong></div>
    <div>${t("openingFixedAssets")}<br><strong>${fmt(r.opening_fixed_assets)}</strong></div>
    <div>${t("openingLoans")}<br><strong>${fmt(r.opening_loans)}</strong></div>
    <div class="in">${t("income")}<br><strong>${fmt(r.income)}</strong></div>
    <div class="out">${t("expense")}<br><strong>${fmt(r.expense)}</strong></div>
    <div>${t("profit")}<br><strong>${fmt(r.profit)}</strong></div>
  </div>

  <h2>${t("sharesValuation")}</h2>
  <div class="valuation-grid">
    <div class="kpi-card">
      <span class="kpi-title">${t("shareCount")}</span>
      <span class="kpi-value">${fmt(r.valuation.share_count)}</span>
    </div>
    <div class="kpi-card kpi-green">
      <span class="kpi-title">${t("eps")}</span>
      <span class="kpi-value">${fmt(r.valuation.eps)}</span>
    </div>
    <div class="kpi-card kpi-gold">
      <span class="kpi-title">${t("bvps")}</span>
      <span class="kpi-value">${fmt(r.valuation.bvps)}</span>
    </div>
  </div>

  <h2>${t("addTx")}</h2>
  <form class="row" id="f">
    <input type="date" name="date" required value="${new Date().toISOString().slice(0,10)}">
    <select name="type">
      <option value="income">${t("income")}</option>
      <option value="expense">${t("expense")}</option>
    </select>
    <select name="category"></select>
    <input name="custom" hidden placeholder="${t("category")}">
    <input name="amount" type="number" step="0.01" min="0.01" required placeholder="${t("amount")}">
    <input name="note" placeholder="${t("note")}">
    <button class="md-btn md-btn-primary">${t("save")}</button>
  </form>

  <h2>${t("transactions")}</h2>
  ${tx.length?`<div class="wrap"><table>
    <tr><th>${t("date")}<th>${t("type")}<th>${t("category")}<th class="n">${t("amount")}<th>${t("note")}<th class="acts">${t("actions")}</tr>
    ${tx.map(x=>{
      const cm=catMeta(x.category);
      const tag=cm.pnl_group?`P&L: ${cm.pnl_group}`:(cm.balance_group?`Bal: ${cm.balance_group}`:'');
      return `<tr class="clickable-row" data-cat="${x.category}" title="${t('clickToViewTx')}">
        <td>${x.date}
        <td class="${x.type==="income"?"in":"out"}">${t(x.type)}
        <td>${esc(catLabel(x.category))}${tag?`<span class="cat-meta-tag">${esc(tag)}</span>`:''}
        <td class="n">${fmt(x.amount)}
        <td>${esc(x.note)}
        <td class="acts"><button class="link" data-e="${x.id}">${t("edit")}</button><button class="link" data-d="${x.id}">${t("delete")}</button>
      </tr>`;
    }).join("")}
  </table></div>`:`<p class="empty">${t("empty")}</p>`}

  <h2>${t("financialReports")}</h2>
  <form id="filter-form" class="filter-row">
    <label>${t("startMonth")} <input type="month" id="filter-from-month" value="${filterFromMonth}"></label>
    <label>${t("endMonth")} <input type="month" id="filter-to-month" value="${filterToMonth}"></label>
    <button class="md-btn md-btn-primary">${t("filter")}</button>
    <button type="button" id="reset-filter" class="md-btn md-btn-outlined">${t("reset")}</button>
  </form>

  <!-- 1. Monthly P&L Statement -->
  <div class="ifrs-card">
    <div class="ifrs-header-title">
      <h3>${t("pnlStatement")}</h3>
      <span class="ifrs-hint">${t("clickToViewTx")}</span>
    </div>
    <div class="wrap">
      <table class="ifrs-table">
        <thead>
          <tr>
            <th>${t("indicator")}</th>
            ${mList.map(m=>`<th class="n">${m}</th>`).join("")}
            <th class="n">${t("totalPeriod")}</th>
          </tr>
        </thead>
        <tbody>
          ${renderPnlRow("revenue", "revenue", false, "in")}
          ${renderPnlRow("cogs", "cogs", false, "out")}
          ${renderPnlRow("grossProfit", "gross_profit", true)}
          ${renderPnlRow("opex", "opex", false, "out")}
          ${renderPnlRow("operatingProfit", "operating_profit", true)}
          ${renderPnlRow("otherIncome", "other_income", false, "in")}
          ${renderPnlRow("otherExpense", "other_expense", false, "out")}
          ${renderPnlRow("financeIncome", "finance_income", false, "in")}
          ${renderPnlRow("financeCost", "finance_cost", false, "out")}
          ${renderPnlRow("profitBeforeTax", "profit_before_tax", true)}
          ${renderPnlRow("tax", "tax", false, "out")}
          <tr class="clickable-row grand-total" title="${t('clickToViewTx')}" data-acc="net_profit">
            <td><strong>${t("netProfit")}</strong></td>
            ${mList.map(m=>`<td class="n"><strong>${fmt(r.monthly_pnl[m]?.net_profit)}</strong></td>`).join("")}
            <td class="n"><strong>${fmt(r.monthly_pnl.total?.net_profit)}</strong></td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>

  <!-- 2. Monthly Balance Sheet -->
  <div class="ifrs-card">
    <div class="ifrs-header-title">
      <h3>${t("balanceSheet")}</h3>
      <span class="ifrs-hint">${t("clickToViewTx")}</span>
    </div>
    <div class="wrap">
      <table class="ifrs-table">
        <thead>
          <tr>
            <th>${t("indicator")}</th>
            ${mList.map(m=>`<th class="n">${t("asOf")} ${m}</th>`).join("")}
            <th class="n">${t("asOf")} ${r.end_month}</th>
          </tr>
        </thead>
        <tbody>
          <tr class="sec-hdr"><td colspan="${mList.length+2}">${t("assets")}</td></tr>
          ${renderBSRow("cashAndEquivalents", bs=>bs.assets.cash, "cash")}
          ${renderBSRow("fixedAssets", bs=>bs.assets.fixed_assets, "fixed_assets")}
          ${renderBSRow("totalAssets", bs=>bs.assets.total_assets, "all", true)}

          <tr class="sec-hdr"><td colspan="${mList.length+2}">${t("liabilities")}</td></tr>
          ${renderBSRow("loans", bs=>bs.liabilities.loans, "loans")}
          ${renderBSRow("totalLiabilities", bs=>bs.liabilities.total_liabilities, "loans", true)}

          <tr class="sec-hdr"><td colspan="${mList.length+2}">${t("equity")}</td></tr>
          ${renderBSRow("initialCapital", bs=>bs.equity.initial_capital, "equity_contribution")}
          ${renderBSRow("contributedCapital", bs=>bs.equity.contributed_capital, "equity_contribution")}
          ${renderBSRow("withdrawnCapital", bs=>bs.equity.withdrawn_capital, "equity_withdrawal")}
          ${renderBSRow("retainedEarnings", bs=>bs.equity.retained_earnings, "all")}
          ${renderBSRow("totalEquity", bs=>bs.equity.total_equity, "all", true)}

          <tr class="clickable-row grand-total" title="${t('clickToViewTx')}" data-acc="all">
            <td><strong>${t("totalLiabilitiesAndEquity")}</strong></td>
            ${mList.map(m=>`<td class="n"><strong>${fmt(r.monthly_balance_sheet[m]?.total_liabilities_and_equity)}</strong></td>`).join("")}
            <td class="n"><strong>${fmt(r.monthly_balance_sheet.total?.total_liabilities_and_equity)}</strong></td>
          </tr>
          <tr class="check-row">
            <td><strong>${t("balanceCheck")}</strong></td>
            ${mList.map(m=>{
              const ok=r.monthly_balance_sheet[m]?.is_balanced;
              return `<td class="n"><span class="badge ${ok?'bg-ok':'bg-err'}">${ok?t("balanced"):t("unbalanced")}</span></td>`;
            }).join("")}
            <td class="n"><span class="badge ${r.monthly_balance_sheet.total?.is_balanced?'bg-ok':'bg-err'}">${r.monthly_balance_sheet.total?.is_balanced?t("balanced"):t("unbalanced")}</span></td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>

  <!-- 3. Monthly Cash Flow Statement -->
  <div class="ifrs-card">
    <div class="ifrs-header-title">
      <h3>${t("cashFlowStatement")}</h3>
      <span class="ifrs-hint">${t("clickToViewTx")}</span>
    </div>
    <div class="wrap">
      <table class="ifrs-table">
        <thead>
          <tr>
            <th>${t("indicator")}</th>
            ${mList.map(m=>`<th class="n">${m}</th>`).join("")}
            <th class="n">${t("totalPeriod")}</th>
          </tr>
        </thead>
        <tbody>
          ${renderCfRow("openingCash", "opening_cash")}
          ${renderCfRow("operatingActivities", "operating")}
          ${renderCfRow("investingActivities", "investing")}
          ${renderCfRow("financingActivities", "financing")}
          ${renderCfRow("netCashFlow", "net_cash_flow", true)}
          <tr class="clickable-row grand-total" title="${t('clickToViewTx')}" data-acc="all">
            <td><strong>${t("endingCash")}</strong></td>
            ${mList.map(m=>`<td class="n"><strong>${fmt(r.monthly_cash_flow[m]?.ending_cash)}</strong></td>`).join("")}
            <td class="n"><strong>${fmt(r.monthly_cash_flow.total?.ending_cash)}</strong></td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>

  <h2>${t("report")}</h2>
  <h3>${t("byCategory")}</h3>
  <div class="wrap">
    <table>
      ${r.categories.map(c=>`<tr class="clickable-row" data-cat="${c.category}" title="${t('clickToViewTx')}"><td>${esc(catLabel(c.category))}<td>${t(c.type)}
      <td class="n">${fmt(c.total)}<td><div class="bar"><i style="width:${c.total/max*100}%;background:var(--${c.type==="income"?"in":"out"})"></i></div></tr>`).join("")}
    </table>
  </div>
  <h3>${t("byMonth")}</h3>
  <div class="wrap">
    <table>
      <tr><th>${t("month")}<th class="n">${t("income")}<th class="n">${t("expense")}<th class="n">${t("profit")}</tr>
      ${r.months.map(m=>`<tr><td>${m.month}<td class="n in">${fmt(m.income)}<td class="n out">${fmt(m.expense)}<td class="n">${fmt(m.income-m.expense)}</tr>`).join("")}
    </table>
  </div>
  <p><button class="md-btn md-btn-outlined" onclick="print()">${t("print")}</button></p>`;

  {
    const f=$("#f");fillCats(f);
    f.type.onchange=()=>fillCats(f);
    f.category.onchange=()=>f.custom.hidden=f.category.value!=="__other";
  }

  $("#f").onsubmit=async e=>{
    e.preventDefault();
    const b=Object.fromEntries(new FormData(e.target));
    b.category=b.category==="__other"?b.custom:b.category;
    delete b.custom;
    if(editId){await api("tx/"+editId,"PUT",b);editId=null}else await api("tx","POST",{...b,company_id:cur});
    render();
  };

  const ff=$("#filter-form");
  if(ff){
    ff.onsubmit=e=>{
      e.preventDefault();
      filterFromMonth=$("#filter-from-month").value;
      filterToMonth=$("#filter-to-month").value;
      render();
    };
    $("#reset-filter").onclick=()=>{
      filterFromMonth="";
      filterToMonth="";
      render();
    };
  }

  app.onclick=async e=>{
    const tr = e.target.closest("tr.clickable-row");
    if(tr && !e.target.dataset.e && !e.target.dataset.d) {
      const acc = tr.dataset.acc || tr.dataset.cat;
      if (acc) {
        const labelText = tr.querySelector("td")?.textContent?.trim() || acc;
        openDrillDown(acc, labelText);
        return;
      }
    }

    const d=e.target.dataset;
    if(d.d&&confirm(t("confirm"))){await api("tx/"+d.d,"DELETE");render()}
    if(d.e){
      const x=tx.find(v=>v.id==d.e);
      editId=x.id;
      const f=$("#f");
      for(const k of["date","type","amount","note"])f[k].value=x[k];
      fillCats(f,x.category);
      f.amount.focus();
    }
  };
}

$("#co").onchange=e=>{
  cur=+e.target.value;
  localStorage.co=cur;
  filterFromMonth="";
  filterToMonth="";
  render();
};
$("#lang").onchange=e=>setLang(e.target.value);
$("#newco").onclick=()=>openCo();
$("#editco").onclick=()=>{if(co().id)openCo(co())};
$("#btn-ai").onclick=()=>openAIDialog();

function openCo(c){
  const d=$("#dlg");
  d.innerHTML=`<form id="cf">
    <h2>${t(c?"edit":"newCompany")}</h2>
    <label>${t("name")}<input name="name" required value="${esc(c?.name)}"></label>
    <label>${t("orgType")}<select name="type">${Object.keys(TY.types).map(k=>`<option value="${k}"${(c?.type||"shop")===k?" selected":""}>${esc(TY.types[k].name[lang])}</option>`).join("")}</select></label>
    <p id="pv"></p>
    
    <div class="section-subtitle">${t("opening")}</div>
    <div class="form-grid-2col">
      <label>${t("openingCash")}<input name="opening_cash" type="number" step="0.01" value="${c?.opening_cash??c?.opening??0}"></label>
      <label>${t("openingFixedAssets")}<input name="opening_fixed_assets" type="number" step="0.01" value="${c?.opening_fixed_assets??0}"></label>
      <label>${t("openingLoans")}<input name="opening_loans" type="number" step="0.01" value="${c?.opening_loans??0}"></label>
      <label>${t("openingEquity")}<input name="opening_equity" type="number" step="0.01" value="${c?.opening_equity??0}"></label>
    </div>

    <div class="section-subtitle">${t("sharesValuation")}</div>
    <label>${t("shareCount")}<input name="share_count" type="number" step="1" min="1" value="${c?.share_count||1000}"></label>

    <div style="margin-top:20px; display:flex; gap:10px;">
      <button class="md-btn md-btn-primary">${t("save")}</button>
      <button type="button" id="x" class="md-btn md-btn-outlined">${t("cancel")}</button>
    </div>
  </form>`;

  const f=$("#cf"),pv=()=>{const y=TY.types[f.type.value];$("#pv").innerHTML=`<b>${t("income")}:</b> ${esc(y.income.map(catLabel).join(", "))}<br><b>${t("expense")}:</b> ${esc(y.expense.map(catLabel).join(", "))}`};
  f.type.onchange=pv;pv();$("#x").onclick=()=>d.close();
  f.onsubmit=async e=>{
    e.preventDefault();
    const b=Object.fromEntries(new FormData(f));
    if(c)await api("companies/"+c.id,"PUT",b);else cur=(await api("companies","POST",b)).id;
    filterFromMonth="";
    filterToMonth="";
    d.close();load();
  };
  d.showModal();
}

fetch("/static/types.json").then(r=>r.json()).then(j=>{TY=j;return setLang(lang)}).then(load);
