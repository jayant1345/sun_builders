let currentDownloadUrl = '/api/download/GSTR-1_SEP-26_AUTOMATED.xlsx';

async function checkStatus() {
    try {
        const resp = await fetch('/api/status');
        const data = await resp.json();
        console.log('Tally & Database Status:', data);

        const sidebarPing = document.getElementById('sidebar-tally-ping');
        const sidebarDot = document.getElementById('sidebar-tally-dot');
        const tallyStatusElem = document.getElementById('tally-status-text');
        const tallyPortBadge = document.getElementById('tally-port-badge');

        const headerBadge = document.getElementById('header-tally-badge');
        const headerPing = document.getElementById('header-tally-ping');
        const headerDot = document.getElementById('header-tally-dot');
        const headerText = document.getElementById('header-tally-text');

        if (data.tally_connected) {
            // Tally port 9000 is genuinely active on this host!
            const comp = (data.loaded_companies && data.loaded_companies.length > 0) ? data.loaded_companies[0] : data.active_company;
            if (comp) {
                if (tallyStatusElem) tallyStatusElem.textContent = 'Tally Prime / ERP';
                if (tallyPortBadge) {
                    tallyPortBadge.textContent = 'PORT 9000 LIVE';
                    tallyPortBadge.className = 'font-mono text-xs text-emerald-700 font-bold';
                }
                if (sidebarDot) sidebarDot.className = 'relative inline-flex rounded-full h-2 w-2 bg-emerald-500';
                if (sidebarPing) {
                    sidebarPing.className = 'animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75';
                    sidebarPing.classList.remove('hidden');
                }
                if (headerBadge) {
                    headerBadge.className = 'hidden xl:flex items-center gap-2 px-3 py-1.5 rounded-full bg-emerald-50 border border-emerald-200 text-emerald-800';
                }
                if (headerText) {
                    headerText.textContent = `Tally 9000: ${comp}`;
                    headerText.className = 'font-mono text-xs text-emerald-700 font-semibold';
                }
                if (headerDot) headerDot.className = 'relative inline-flex rounded-full h-2 w-2 bg-emerald-500';
                if (headerPing) {
                    headerPing.className = 'animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75';
                    headerPing.classList.remove('hidden');
                }
            } else {
                if (tallyStatusElem) tallyStatusElem.textContent = 'Tally 9000 (No Co.)';
                if (tallyPortBadge) {
                    tallyPortBadge.textContent = 'SELECT COMPANY';
                    tallyPortBadge.className = 'font-mono text-[10px] text-amber-700 font-bold bg-amber-50 px-1.5 py-0.5 rounded border border-amber-200';
                }
                if (sidebarDot) sidebarDot.className = 'relative inline-flex rounded-full h-2 w-2 bg-amber-500';
                if (sidebarPing) sidebarPing.classList.add('hidden');

                if (headerBadge) {
                    headerBadge.className = 'hidden xl:flex items-center gap-2 px-3 py-1.5 rounded-full bg-amber-50 border border-amber-200 text-amber-800';
                }
                if (headerText) {
                    headerText.textContent = 'Tally Port 9000 Open: Please Open Company in Tally';
                    headerText.className = 'font-mono text-xs text-amber-800 font-semibold';
                }
                if (headerDot) headerDot.className = 'relative inline-flex rounded-full h-2 w-2 bg-amber-500';
                if (headerPing) headerPing.classList.add('hidden');
            }

            const syncSourceText = document.getElementById('sync-source-text');
            if (syncSourceText) syncSourceText.textContent = comp ? `Port 9000: ${comp}` : 'Port 9000 Connected';

        } else {
            // Tally is closed or port 9000 is not reachable
            if (tallyStatusElem) tallyStatusElem.textContent = data.is_cloud ? 'Railway Cloud' : 'Tally Service';
            if (tallyPortBadge) {
                tallyPortBadge.textContent = 'PORT 9000 OFFLINE';
                tallyPortBadge.className = 'font-mono text-[10px] text-slate-500 font-bold bg-slate-100 px-1.5 py-0.5 rounded';
            }
            if (sidebarDot) sidebarDot.className = 'relative inline-flex rounded-full h-2 w-2 bg-slate-400';
            if (sidebarPing) sidebarPing.classList.add('hidden');

            if (headerBadge) {
                headerBadge.className = 'hidden xl:flex items-center gap-2 px-3 py-1.5 rounded-full bg-slate-100 border border-slate-200 text-slate-600';
            }
            if (headerText) {
                headerText.textContent = 'Tally Port 9000: OFFLINE (Tally Closed)';
                headerText.className = 'font-mono text-xs text-slate-600 font-semibold';
            }
            if (headerDot) headerDot.className = 'relative inline-flex rounded-full h-2 w-2 bg-slate-400';
            if (headerPing) headerPing.classList.add('hidden');

            const syncSourceText = document.getElementById('sync-source-text');
            if (syncSourceText) syncSourceText.textContent = 'Port 9000 Offline (Tally Closed)';
        }

        const barComp = document.getElementById('bar-active-company');
        if (barComp) {
            barComp.textContent = data.active_company ? data.active_company : 'Tally Offline (Please open company in Tally)';
        }
        if (data.active_project_code) {
            const vSel = document.getElementById('select-voucher-project');
            if (vSel && (!vSel.value || vSel.value === '010010') && data.active_project_code !== '010010') {
                vSel.value = data.active_project_code;
                loadRealVouchers(data.active_project_code);
            }
        }
    } catch (e) {
        console.warn('Status check warning:', e);
    }
}

function appendLog(level, message) {
    const logBoxes = document.querySelectorAll('.terminal-scrollbar');
    if (!logBoxes.length) return;
    const now = new Date();
    const timeStr = now.toTimeString().split(' ')[0] + '.' + String(now.getMilliseconds()).padStart(3, '0');
    
    let colorClass = 'text-primary';
    if (level === 'EXEC' || level === 'SUCCESS' || level === 'READY') colorClass = 'text-secondary';
    if (level === 'RULE') colorClass = 'text-tertiary';
    if (level === 'ERROR') colorClass = 'text-error';

    logBoxes.forEach(box => {
        const row = document.createElement('div');
        row.className = 'flex items-start gap-2';
        row.innerHTML = `<span class="text-outline select-none font-mono text-label-sm">[${timeStr}]</span>
                         <span class="${colorClass} font-medium">${level}</span>
                         <span>${message}</span>`;
        box.appendChild(row);
        box.scrollTop = box.scrollHeight;
    });
}

function switchTab(tabId) {
    if (!tabId) tabId = 'overview';
    
    // Normalize aliases
    const aliasMap = {
        'compliance': 'overview',
        'audit-trail': 'audit',
        'itc-ledger': 'itc',
        'reports': 'returns'
    };
    if (aliasMap[tabId]) tabId = aliasMap[tabId];

    // Hide all tab panes
    const panes = document.querySelectorAll('.tab-pane');
    let found = false;
    panes.forEach(pane => {
        if (pane.id === `tab-${tabId}`) {
            pane.classList.remove('hidden');
            found = true;
        } else {
            pane.classList.add('hidden');
        }
    });

    if (!found) {
        // Fallback to overview
        tabId = 'overview';
        const overviewPane = document.getElementById('tab-overview');
        if (overviewPane) overviewPane.classList.remove('hidden');
    }

    // Update left sidebar navigation items
    const navTabs = document.querySelectorAll('.nav-tab');
    navTabs.forEach(link => {
        const target = link.getAttribute('data-tab');
        if (target === tabId) {
            link.className = 'nav-tab flex items-center gap-3 px-3.5 py-2.5 rounded-xl bg-blue-50 text-blue-700 font-semibold border-l-4 border-blue-600 text-sm transition-all duration-150 shadow-xs';
        } else {
            link.className = 'nav-tab flex items-center gap-3 px-3.5 py-2.5 rounded-xl text-slate-600 hover:text-slate-900 hover:bg-slate-100 text-sm font-medium transition-all duration-150';
        }
    });

    // Update top nav tabs if present
    const topTabs = document.querySelectorAll('.top-nav-tab');
    topTabs.forEach(topLink => {
        const target = topLink.getAttribute('data-tab');
        if (target === tabId) {
            topLink.className = 'top-nav-tab text-blue-700 border-b-2 border-blue-600 pb-1 font-semibold text-sm transition-colors';
        } else {
            topLink.className = 'top-nav-tab text-slate-500 hover:text-slate-900 text-sm font-medium transition-colors';
        }
    });

    // Update browser URL hash cleanly without reload
    if (window.location.hash !== `#${tabId}`) {
        history.pushState(null, null, `#${tabId}`);
    }

    // If switching to vouchers or overview, ensure real vouchers are loaded
    if (tabId === 'vouchers') {
        tabId = 'overview';
        const overviewPane = document.getElementById('tab-overview');
        if (overviewPane) overviewPane.classList.remove('hidden');
        const vHub = document.getElementById('voucher-hub-section');
        if (vHub) {
            setTimeout(() => vHub.scrollIntoView({ behavior: 'smooth' }), 100);
        }
    }

    const vSel = document.getElementById('select-voucher-project');
    loadRealVouchers(vSel ? vSel.value : '010010');

    if (tabId === 'units') {
        const uSel = document.getElementById('select-units-project');
        loadUnits(uSel ? uSel.value : '010000');
    }

    if (tabId === 'audit') {
        loadActivityLogs();
    }

    // Scroll to top of main content unless targeted
    if (window.location.hash !== '#voucher-hub-section' && window.location.hash !== '#vouchers') {
        window.scrollTo({ top: 0, behavior: 'smooth' });
    }
}

function ensureProjectInSelect(sel, code, label) {
    if (!sel || !code) return;
    for (let i = 0; i < sel.options.length; i++) {
        if (sel.options[i].value === code) {
            if (label && (!sel.options[i].textContent || sel.options[i].textContent.includes('Project ('))) {
                sel.options[i].textContent = label;
            }
            return;
        }
    }
    const opt = document.createElement('option');
    opt.value = code;
    opt.textContent = label || `Company ${code}`;
    opt.className = 'bg-surface-container text-on-surface';
    sel.appendChild(opt);
}

let vouchersLoaded = false;
let currentVoucherCategory = 'income';

function updateVoucherCategoryButtons() {
    document.querySelectorAll('.voucher-category-btn').forEach(btn => {
        if (btn.getAttribute('data-category') === currentVoucherCategory) {
            btn.className = 'voucher-category-btn flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold transition-all bg-white text-blue-700 shadow-xs';
        } else {
            btn.className = 'voucher-category-btn flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold transition-all text-slate-500 hover:text-slate-800';
        }
    });
}

async function loadRealVouchers(projectKey, month, year) {
    try {
        const vSel = document.getElementById('select-voucher-project');
        const hSel = document.getElementById('select-header-project');
        const mSel = document.getElementById('select-voucher-month');
        const ySel = document.getElementById('select-voucher-year');

        const targetKey = projectKey || (vSel ? vSel.value : '010010');
        const targetMonth = month !== undefined ? month : (mSel ? mSel.value : 'ALL');
        const targetYear = year !== undefined ? year : (ySel ? ySel.value : 'ALL');
        
        ensureProjectInSelect(vSel, targetKey, `🏢 Project (${targetKey})`);
        ensureProjectInSelect(hSel, targetKey, `Project (${targetKey})`);
        if (vSel && vSel.value !== targetKey) vSel.value = targetKey;
        if (hSel && hSel.value !== targetKey) hSel.value = targetKey;
        if (mSel && month !== undefined && mSel.value !== targetMonth) mSel.value = targetMonth;
        if (ySel && year !== undefined && ySel.value !== targetYear) ySel.value = targetYear;

        updateVoucherCategoryButtons();
        const resp = await fetch(`/api/vouchers?project=${encodeURIComponent(targetKey)}&month=${encodeURIComponent(targetMonth)}&year=${encodeURIComponent(targetYear)}&category=${encodeURIComponent(currentVoucherCategory)}`);
        const data = await resp.json();
        if (data.status === 'success' && data.vouchers) {
            vouchersLoaded = true;

            // Ensure selects have rich label with count and are selected
            if (vSel) {
                ensureProjectInSelect(vSel, data.company_code, `🏢 ${data.project_name} (${data.company_code}) — ${data.count} Vouchers`);
                vSel.value = data.company_code;
            }
            if (hSel) {
                ensureProjectInSelect(hSel, data.company_code, `${data.project_name} (${data.company_code})`);
                hSel.value = data.company_code;
            }

            // Update active company badge & period badge
            const activeBadge = document.getElementById('active-company-badge');
            if (activeBadge) {
                activeBadge.textContent = `Company: ${data.company_code} (${data.project_name}) Loaded`;
            }
            const periodBadge = document.getElementById('voucher-active-period-badge');
            if (periodBadge) {
                periodBadge.textContent = `Period: ${data.period_display || 'ALL'}`;
            }
            const incomeCountBadge = document.getElementById('voucher-category-income-count');
            if (incomeCountBadge) {
                incomeCountBadge.textContent = typeof data.income_count === 'number' ? `(${data.income_count})` : '';
            }

            const tbody = document.getElementById('voucher-table-body');
            if (tbody) {
                tbody.innerHTML = '';
                if (data.vouchers.length === 0) {
                    tbody.innerHTML = `<tr><td colspan="9" class="text-center py-8 text-on-surface-variant font-sans">
                        <div class="flex flex-col items-center justify-center gap-2">
                            <span class="material-symbols-outlined text-outline text-3xl">receipt_long</span>
                            <span class="font-bold text-on-surface">No ${currentVoucherCategory === 'income' ? 'Income (Flat/Shop Receipt)' : ''} Vouchers for ${data.project_name} (${data.company_code}) in Period ${data.period_display || 'Selected'}</span>
                            <span class="text-xs text-on-surface-variant max-w-md">No transactions recorded for this selected month and year. Switch the filter to "All Months" or another period, ${currentVoucherCategory === 'income' ? 'toggle to "All Vouchers" to check purchase/expense entries, ' : ''}or run Tally Sync.</span>
                        </div>
                    </td></tr>`;
                } else {
                    data.vouchers.forEach(v => {
                        const tr = document.createElement('tr');
                        const unitDisplay = (v.flat_no && v.flat_no !== 'undefined') ? v.flat_no : ((v.unit && v.unit !== 'undefined') ? v.unit : '—');
                        const memberDisplay = (v.member_name && v.member_name !== 'undefined') ? v.member_name : ((v.name && v.name !== 'undefined') ? v.name : 'Member');
                        const hasUnit = unitDisplay && unitDisplay !== '—';

                        tr.className = `hover:bg-primary/10 transition-colors ${hasUnit ? 'cursor-pointer' : ''}`;
                        if (hasUnit) {
                            tr.setAttribute('title', `Click to view full records & statement for Unit ${unitDisplay}`);
                            tr.addEventListener('click', (e) => {
                                if (e.target.closest('.btn-edit-override')) return;
                                openUnitHistory(data.company_code || '010010', unitDisplay);
                            });
                        }
                        
                        let badgeHtml = '';
                        if (v.badge_type === 'bu_review') {
                            badgeHtml = `<span class="px-2 py-0.5 rounded text-xs bg-orange-500/10 text-orange-600 border border-orange-500/30 font-medium">⚠ ${v.classification}</span>`;
                        } else if (v.badge_type === 'review') {
                            badgeHtml = `<span class="px-2 py-0.5 rounded text-xs bg-red-500/10 text-red-600 border border-red-500/30 font-medium">⚠ ${v.classification}</span>`;
                        } else if (v.badge_type === 'excluded_manual') {
                            badgeHtml = `<span class="px-2 py-0.5 rounded text-xs bg-purple-500/10 text-purple-600 border border-purple-500/30 font-medium">✎ ${v.classification}</span>`;
                        } else if (v.badge_type === 'pass_through') {
                            badgeHtml = `<span class="px-2 py-0.5 rounded text-xs bg-sky-500/10 text-sky-600 border border-sky-500/30 font-medium">${v.classification}</span>`;
                        } else if (v.badge_type === 'creditor' || v.badge_type === 'expense') {
                            badgeHtml = `<span class="px-2 py-0.5 rounded text-xs bg-slate-400/10 text-slate-500 border border-slate-400/30 font-medium">${v.classification}</span>`;
                        } else if (v.badge_type === 'cancelled') {
                            badgeHtml = `<span class="px-2 py-0.5 rounded text-xs bg-red-400/10 text-red-500 border border-red-400/30 font-medium line-through">${v.classification}</span>`;
                        } else if (v.badge_type === 'exempt' || (v.classification && v.classification.toLowerCase().includes('exempt'))) {
                            badgeHtml = `<span class="px-2 py-0.5 rounded text-xs bg-secondary/10 text-secondary border border-secondary/30 font-medium">${v.classification}</span>`;
                        } else if (v.badge_type === 'taxable-5' || (v.classification && v.classification.includes('5%'))) {
                            badgeHtml = `<span class="px-2 py-0.5 rounded text-xs bg-amber-500/10 text-amber-400 border border-amber-500/30 font-medium">${v.classification}</span>`;
                        } else if (v.badge_type === 'taxable-1' || (v.classification && v.classification.includes('1%'))) {
                            badgeHtml = `<span class="px-2 py-0.5 rounded text-xs bg-primary/10 text-primary border border-primary/30 font-medium">${v.classification}</span>`;
                        } else {
                            badgeHtml = `<span class="px-2 py-0.5 rounded text-xs bg-surface-container text-on-surface border border-outline-variant font-medium">${v.classification}</span>`;
                        }

                        const formattedCr = Number(v.cr_amount || 0).toLocaleString('en-IN', { maximumFractionDigits: 0 });
                        const pencilClass = v.has_override ? 'text-blue-600' : 'text-slate-300 hover:text-slate-500';

                        tr.innerHTML = `
                            <td class="py-2.5 px-3 text-on-surface">${v.date}</td>
                            <td class="py-2.5 px-3 text-primary font-semibold font-mono">${v.vch_no}</td>
                            <td class="py-2.5 px-3 font-mono font-bold">
                                <span class="text-secondary bg-secondary/10 hover:bg-secondary/20 hover:scale-105 transition-all px-2.5 py-1 rounded border border-secondary/20 inline-block my-1 ${hasUnit ? 'cursor-pointer shadow-xs' : ''}" title="${hasUnit ? 'Click to view full statement for Unit ' + unitDisplay : ''}">${unitDisplay}</span>
                            </td>
                            <td class="py-2.5 px-4 font-sans text-on-surface font-medium">${memberDisplay}</td>
                            <td class="py-2.5 px-3 text-on-surface-variant font-sans">${v.project}</td>
                            <td class="py-2.5 px-3 text-on-surface-variant font-sans">${v.type}</td>
                            <td class="py-2.5 px-3 text-right text-on-surface font-semibold font-mono">₹${formattedCr}</td>
                            <td class="py-2.5 px-4 font-sans">${badgeHtml}</td>
                            <td class="py-2.5 px-2 text-center">
                                <button type="button" class="btn-edit-override p-1 rounded hover:bg-slate-100 transition-colors ${pencilClass}" title="${v.has_override ? 'Classification manually overridden - click to edit' : 'Correct classification'}">
                                    <span class="material-symbols-outlined text-[16px]">edit</span>
                                </button>
                            </td>
                        `;
                        tr.querySelector('.btn-edit-override').addEventListener('click', (e) => {
                            e.stopPropagation();
                            openOverrideModal(v);
                        });
                        tbody.appendChild(tr);
                    });
                }
            }

            // Update stats cards
            const totalTitle = document.getElementById('vouchers-metric-title-total');
            if (totalTitle) totalTitle.textContent = `${data.project_name} Vouchers (${data.period_display || 'ALL'})`;
            const totalElem = document.getElementById('vouchers-metric-total');
            if (totalElem) totalElem.textContent = `${data.count} Vouchers`;
            const totalSub = document.getElementById('vouchers-metric-sub-total');
            if (totalSub) {
                const grossCr = (Number(data.total_gross || 0) / 10000000).toFixed(2);
                totalSub.textContent = `Gross: ₹${grossCr} Cr | Co: ${data.company_code}`;
            }
            
            const exemptTitle = document.getElementById('vouchers-metric-title-exempt');
            if (exemptTitle) exemptTitle.textContent = data.has_bu ? `Post-BU Exempt (${data.project_name})` : 'Post-BU Exemption Status';
            const exemptElem = document.getElementById('vouchers-metric-exempt');
            if (exemptElem) {
                const exCr = data.post_bu_exempt > 0 ? `₹${(data.post_bu_exempt / 10000000).toFixed(2)} Cr` : '₹0.00 Cr';
                exemptElem.textContent = exCr;
            }
            const exemptSub = document.getElementById('vouchers-metric-sub-exempt');
            if (exemptSub) {
                exemptSub.textContent = (data.has_bu && data.bu_permission_date) ? `Post ${data.bu_permission_date} Cutoff` : 'Under Construction (No BU Cutoff)';
            }

            const exclElem = document.getElementById('vouchers-metric-exclusions');
            if (exclElem) {
                if (data.total_deductions >= 10000000) {
                    exclElem.textContent = `₹${(data.total_deductions / 10000000).toFixed(2)} Cr`;
                } else if (data.total_deductions > 0) {
                    exclElem.textContent = `₹${Number(data.total_deductions).toLocaleString('en-IN')}`;
                } else {
                    exclElem.textContent = `₹0`;
                }
            }

            const taxElem = document.getElementById('vouchers-metric-taxable');
            if (taxElem) {
                const taxCr = (data.total_taxable / 10000000).toFixed(2);
                taxElem.textContent = `₹${taxCr} Cr`;
            }
            const taxSub = document.getElementById('vouchers-metric-sub-taxable');
            if (taxSub) {
                if (data.company_code === '010011') {
                    const gstAmountL = ((data.total_taxable * 0.05) / 100000).toFixed(2);
                    taxSub.textContent = `Output GST @ 5%: ₹${gstAmountL} L`;
                } else if (data.total_taxable === 0 && data.post_bu_exempt > 0) {
                    taxSub.textContent = `All Collections Post-BU Exempt (₹0 GST)`;
                } else {
                    const gstAmountL = ((data.total_taxable * 0.01) / 100000).toFixed(2);
                    taxSub.textContent = `Output GST @ 1%: ₹${gstAmountL} L`;
                }
            }

            // Update header description
            const headerDesc = document.getElementById('vouchers-header-desc');
            if (headerDesc) {
                headerDesc.textContent = `Live streaming & offline ledger vouchers extracted from Company ${data.company_code} (${data.project_name} - ${data.count} Vouchers Loaded)`;
            }

            // Dynamically update Overview Tab KPI Cards to match selected project
            updateOverviewCards(data);
        }
    } catch (e) {
        console.warn('Failed to load vouchers dynamically:', e);
    }
}

function updateOverviewCards(data) {
    if (!data) return;

    // 1. Card 1: Project Compliance Trigger
    const titleElem = document.getElementById('overview-project-title');
    if (titleElem) {
        titleElem.textContent = `${data.project_name} Compliance Rule`;
    }

    const badgeElem = document.getElementById('overview-project-status-badge');
    const badgeText = document.getElementById('overview-project-status-text');
    const buDateElem = document.getElementById('overview-bu-date');
    const buDescElem = document.getElementById('overview-bu-rule-desc');
    const exemptAmtElem = document.getElementById('overview-exempt-amount');
    const exemptLblElem = document.getElementById('overview-exempt-label');
    const unitsBadge = document.getElementById('overview-units-badge');

    if (data.has_bu && data.bu_permission_date) {
        if (badgeElem) badgeElem.className = 'inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-secondary/10 text-secondary border border-secondary/30';
        if (badgeText) badgeText.textContent = 'Statutory Cutoff Activated';
        if (buDateElem) buDateElem.textContent = `${data.bu_permission_date} (${data.authority || 'Competent Authority'})`;
        if (buDescElem) {
            buDescElem.innerHTML = `<strong class="text-secondary font-medium">Statutory Rule:</strong> All advances and installment receipts received after <span class="text-on-surface font-semibold underline decoration-secondary">${data.bu_permission_date}</span> are <strong class="text-secondary font-semibold">100% EXEMPT</strong> under Schedule III Entry 5 (Sale of Land &amp; Completed Building).`;
        }
        if (exemptAmtElem) {
            const exCr = data.post_bu_exempt > 0 ? `₹${(data.post_bu_exempt / 10000000).toFixed(2)} Cr` : '₹0.00 Cr';
            exemptAmtElem.textContent = exCr;
        }
        if (exemptLblElem) exemptLblElem.textContent = `Post-BU Total Exemptions Applied (${data.project_name})`;
    } else {
        if (badgeElem) badgeElem.className = 'inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-primary/10 text-primary border border-primary/30';
        if (badgeText) badgeText.textContent = 'Under Construction';
        if (buDateElem) buDateElem.textContent = 'Under Construction (No BU Cutoff)';
        if (buDescElem) {
            buDescElem.innerHTML = `<strong class="text-primary font-medium">Statutory Rule:</strong> Project is classified as <span class="text-on-surface font-semibold">Under Construction</span>. All eligible collections are classified as <strong>Taxable @ ${data.rate || '5%'}</strong> with ₹0 post-BU exemption.`;
        }
        if (exemptAmtElem) exemptAmtElem.textContent = '₹0.00 Cr';
        if (exemptLblElem) exemptLblElem.textContent = `Post-BU Exemption Status (Under Construction)`;
    }

    if (unitsBadge) {
        unitsBadge.textContent = `${data.count} vouchers loaded`;
    }

    // 2. Card 2: Non-GST Exclusions
    const exclAmtElem = document.getElementById('overview-exclusions-amount');
    const exclLblElem = document.getElementById('overview-exclusions-label');
    if (exclAmtElem) {
        if (data.total_deductions >= 10000000) {
            exclAmtElem.textContent = `₹${(data.total_deductions / 10000000).toFixed(2)} Cr`;
        } else if (data.total_deductions > 0) {
            exclAmtElem.textContent = `₹${(data.total_deductions / 100000).toFixed(2)} Lakhs`;
        } else {
            exclAmtElem.textContent = '₹0';
        }
    }
    if (exclLblElem) {
        exclLblElem.textContent = `Total Exclusions (${data.project_name})`;
    }

    // 3. Card 3: Highlight active rate row in Tax Rate Slabs Matrix
    const rowAfford = document.getElementById('rate-row-affordable');
    const rowStandard = document.getElementById('rate-row-standard');
    const rowComm = document.getElementById('rate-row-commercial');

    [rowAfford, rowStandard, rowComm].forEach(r => {
        if (r) {
            r.classList.remove('ring-2', 'ring-secondary', 'bg-secondary/15', 'ring-primary', 'bg-primary/15', 'ring-tertiary', 'bg-tertiary/15');
        }
    });

    if (data.company_code === '010009' || (data.rate && data.rate.includes('18%'))) {
        if (rowComm) rowComm.classList.add('ring-2', 'ring-tertiary', 'bg-tertiary/15');
    } else if (data.rate && data.rate.includes('1%')) {
        if (rowAfford) rowAfford.classList.add('ring-2', 'ring-secondary', 'bg-secondary/15');
    } else {
        if (rowStandard) rowStandard.classList.add('ring-2', 'ring-primary', 'bg-primary/15');
    }

    // 4. Highlight project row in the Overview Table
    const allRows = document.querySelectorAll('#project-table-body tr');
    allRows.forEach(r => r.classList.remove('bg-primary/10', 'border-l-4', 'border-l-secondary', 'border-l-primary'));
    const targetBadge = document.getElementById(`proj-bu-badge-${data.company_code}`);
    if (targetBadge) {
        const targetRow = targetBadge.closest('tr');
        if (targetRow) {
            targetRow.classList.add('bg-primary/10', 'border-l-4', 'border-l-secondary');
        }
    }
}

let currentUnitsData = [];
let currentUnitsFilters = { block: 'ALL', status: 'ALL', search: '' };

async function loadUnits(projectKey) {
    const pSel = document.getElementById('select-units-project');
    const targetKey = projectKey || (pSel ? pSel.value : '010000');
    if (pSel && pSel.value !== targetKey) pSel.value = targetKey;

    const tbody = document.getElementById('units-table-body');
    if (tbody) {
        tbody.innerHTML = `<tr><td colspan="9" class="text-center py-8 text-slate-400 font-sans">Loading units...</td></tr>`;
    }

    try {
        const resp = await fetch(`/api/units?project=${encodeURIComponent(targetKey)}&block=ALL`);
        const data = await resp.json();
        if (data.status !== 'success') return;

        currentUnitsData = data.units || [];
        currentUnitsFilters.block = 'ALL';

        const blockSel = document.getElementById('select-units-block');
        if (blockSel) {
            blockSel.innerHTML = '<option value="ALL">All Blocks</option>' +
                (data.blocks || []).map(b => `<option value="${b}">Block ${b}</option>`).join('');
        }

        const subtitle = document.getElementById('units-tab-subtitle');
        if (subtitle) subtitle.textContent = `${data.project_name} — ${data.count} units in master inventory (block/size from CA unit list, payments from synced Tally vouchers)`;

        renderUnitsTable();
    } catch (err) {
        if (tbody) tbody.innerHTML = `<tr><td colspan="9" class="text-center py-8 text-red-500 font-sans">Failed to load units: ${err.message}</td></tr>`;
    }
}

function renderUnitsTable() {
    const tbody = document.getElementById('units-table-body');
    if (!tbody) return;

    let rows = currentUnitsData;
    if (currentUnitsFilters.block !== 'ALL') {
        rows = rows.filter(u => u.block === currentUnitsFilters.block);
    }
    if (currentUnitsFilters.status !== 'ALL') {
        rows = rows.filter(u => u.status === currentUnitsFilters.status);
    }
    if (currentUnitsFilters.search) {
        const q = currentUnitsFilters.search.toLowerCase();
        rows = rows.filter(u =>
            (u.unit_no || '').toLowerCase().includes(q) ||
            (u.owners || []).join(' ').toLowerCase().includes(q)
        );
    }

    const summaryBadge = document.getElementById('units-summary-badge');
    if (summaryBadge) {
        const paidCount = currentUnitsData.filter(u => u.status === 'paid').length;
        summaryBadge.textContent = `Showing ${rows.length} of ${currentUnitsData.length} units (${paidCount} with payment history)`;
    }

    if (rows.length === 0) {
        tbody.innerHTML = `<tr><td colspan="9" class="text-center py-8 text-slate-400 font-sans">
            <div class="flex flex-col items-center justify-center gap-1.5">
                <span class="material-symbols-outlined text-[28px] text-slate-300">apartment</span>
                <span class="font-bold text-slate-600">No units match the current filters</span>
            </div>
        </td></tr>`;
        return;
    }

    tbody.innerHTML = '';
    const projectKey = document.getElementById('select-units-project')?.value || '010000';
    rows.forEach(u => {
        const tr = document.createElement('tr');
        tr.className = 'hover:bg-blue-50/40 transition-colors cursor-pointer';
        tr.addEventListener('click', () => openUnitHistory(projectKey, u.unit_no));

        const ownersText = (u.owners && u.owners.length) ? u.owners.join(', ') : '—';
        const statusBadge = u.status === 'paid'
            ? `<span class="px-2 py-0.5 rounded text-xs bg-emerald-50 text-emerald-700 border border-emerald-200 font-medium">Paid</span>`
            : `<span class="px-2 py-0.5 rounded text-xs bg-slate-100 text-slate-500 border border-slate-200 font-medium">No Payments</span>`;
        const formattedPaid = Number(u.total_paid || 0).toLocaleString('en-IN', { maximumFractionDigits: 0 });
        const usageFloor = [u.usage_type, u.floor].filter(Boolean).join(' / ') || '—';

        tr.innerHTML = `
            <td class="py-2.5 px-4 font-mono font-bold text-secondary bg-secondary/10 px-2 py-0.5 rounded border border-secondary/20 inline-block my-1.5">${u.unit_no}</td>
            <td class="py-2.5 px-3 text-on-surface-variant font-sans">${u.block || '—'}</td>
            <td class="py-2.5 px-3 text-on-surface-variant font-sans">${usageFloor}</td>
            <td class="py-2.5 px-3 text-right text-on-surface font-mono">${Number(u.size_sqft || 0).toLocaleString('en-IN')}</td>
            <td class="py-2.5 px-4 font-sans text-on-surface font-medium">${ownersText}</td>
            <td class="py-2.5 px-3 text-right text-on-surface font-semibold font-mono">${u.total_paid ? '₹' + formattedPaid : '—'}</td>
            <td class="py-2.5 px-3 text-center text-on-surface font-mono">${u.payment_count}</td>
            <td class="py-2.5 px-3 text-on-surface-variant font-sans">${u.last_payment_date || '—'}</td>
            <td class="py-2.5 px-3 text-center">${statusBadge}</td>
        `;
        tbody.appendChild(tr);
    });
}

let currentActiveUnitModal = null;
let currentUnitVouchersList = [];

async function openUnitHistory(projectKey, unitNo) {
    if (!unitNo || unitNo === '—' || unitNo === 'undefined') return;
    currentActiveUnitModal = { projectKey, unitNo };

    const modal = document.getElementById('unit-history-modal');
    const badgeEl = document.getElementById('unit-modal-badge');
    const title = document.getElementById('unit-history-title');
    const projEl = document.getElementById('unit-modal-project-name');
    const ownerEl = document.getElementById('unit-modal-owner-name');
    const buBadge = document.getElementById('unit-modal-bu-badge');
    const rateBadge = document.getElementById('unit-modal-rate-badge');
    const specsEl = document.getElementById('unit-modal-specs');
    const ownersBox = document.getElementById('unit-history-owners');
    const notesBox = document.getElementById('unit-history-transfer-notes');
    const tableBody = document.getElementById('unit-modal-table-body');
    const vchCountBadge = document.getElementById('unit-modal-voucher-count-badge');
    const searchInput = document.getElementById('unit-modal-search');
    const timeline = document.getElementById('unit-history-timeline');

    if (badgeEl) badgeEl.textContent = `Unit ${unitNo}`;
    if (title) title.textContent = `Unit ${unitNo} Statement & Ledger`;
    if (projEl) projEl.textContent = `Project ${projectKey}`;
    if (ownerEl) ownerEl.textContent = 'Loading...';
    if (ownersBox) ownersBox.innerHTML = '';
    if (notesBox) notesBox.innerHTML = '';
    if (tableBody) tableBody.innerHTML = `<tr><td colspan="10" class="text-center py-8 text-slate-400 font-sans">Loading all records for Unit ${unitNo}...</td></tr>`;
    if (timeline) timeline.innerHTML = '';
    if (searchInput) searchInput.value = '';

    if (modal) modal.classList.remove('hidden');

    try {
        const resp = await fetch(`/api/units/history?project=${encodeURIComponent(projectKey)}&unit=${encodeURIComponent(unitNo)}`);
        const data = await resp.json();
        if (data.status !== 'success') {
            if (tableBody) tableBody.innerHTML = `<tr><td colspan="10" class="text-center py-6 text-red-500 font-sans">${data.message || 'Error loading unit data'}</td></tr>`;
            return;
        }

        // Header updates
        if (badgeEl) badgeEl.textContent = `Unit ${data.unit_no}`;
        if (title) title.textContent = `Unit ${data.unit_no} Statement & History`;
        if (projEl) projEl.textContent = `${data.project_name} (${data.project_key})`;
        if (ownerEl) ownerEl.textContent = data.current_owner || (data.owners && data.owners.length ? data.owners[data.owners.length - 1] : 'Member');

        if (buBadge) {
            if (data.is_exempt) {
                buBadge.className = 'px-2.5 py-0.5 rounded-full text-xs font-bold bg-emerald-100 text-emerald-800 border border-emerald-200';
                buBadge.textContent = 'Exempt Post-BU (Schedule III)';
            } else {
                buBadge.className = 'px-2.5 py-0.5 rounded-full text-xs font-bold bg-amber-100 text-amber-800 border border-amber-200';
                buBadge.textContent = data.bu_status_label || 'Taxable (Pre-BU)';
            }
        }

        const toggleBuBtn = document.getElementById('btn-toggle-unit-bu');
        const toggleBuText = document.getElementById('btn-toggle-unit-bu-text');
        if (toggleBuBtn && toggleBuText) {
            toggleBuBtn.classList.remove('hidden');
            if (data.is_exempt) {
                toggleBuBtn.className = 'flex items-center gap-1.5 px-3 py-1.5 rounded-xl border border-amber-300 bg-amber-50 hover:bg-amber-100 text-amber-900 text-xs font-bold shadow-xs transition-colors';
                toggleBuText.textContent = 'Switch to Pre-BU (Taxable)';
                toggleBuBtn.title = 'Mark all vouchers for this unit as Pre-BU Taxable';
            } else {
                toggleBuBtn.className = 'flex items-center gap-1.5 px-3 py-1.5 rounded-xl border border-emerald-300 bg-emerald-50 hover:bg-emerald-100 text-emerald-800 text-xs font-bold shadow-xs transition-colors';
                toggleBuText.textContent = 'Mark as Post-BU (Exempt 0% GST)';
                toggleBuBtn.title = 'Mark all vouchers for this unit as Post-BU Purchase (Exempt under Schedule III)';
            }
            toggleBuBtn.onclick = async () => {
                const newStatus = data.is_exempt ? 'before_bu' : 'after_bu';
                const promptMsg = data.is_exempt 
                    ? `Switch Unit ${data.unit_no} to Pre-BU (Taxable)? This will apply GST to receipts.`
                    : `Mark Unit ${data.unit_no} as Post-BU Purchase (Exempt)? Under Schedule III, all receipts will be 0% GST (Exempt).`;
                if (!confirm(promptMsg)) return;

                toggleBuBtn.disabled = true;
                toggleBuText.textContent = 'Updating...';
                try {
                    const r = await fetch('/api/units/override-bu', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            project: data.project_key,
                            unit: data.unit_no,
                            bu_status: newStatus,
                            note: `Set to ${newStatus} from Unit Statement modal`
                        })
                    });
                    const res = await r.json();
                    if (res.status === 'success') {
                        await openUnitHistory(data.project_key, data.unit_no);
                        const projectSel = document.getElementById('select-voucher-project');
                        if (projectSel) loadRealVouchers(projectSel.value);
                    } else {
                        alert('Could not update: ' + (res.message || 'Unknown error'));
                    }
                } catch (e) {
                    alert('Network error: ' + e.message);
                } finally {
                    toggleBuBtn.disabled = false;
                }
            };
        }

        if (rateBadge) {
            rateBadge.className = 'px-2.5 py-0.5 rounded-full text-xs font-bold bg-blue-100 text-blue-800 border border-blue-200';
            rateBadge.textContent = data.rate_label || `${data.rate_pct}% Rate`;
        }

        const buDateBadge = document.getElementById('unit-modal-bu-date-badge');
        const buDateText = document.getElementById('unit-modal-bu-date-text');
        const buDateSub = document.getElementById('unit-modal-bu-date-sub');

        if (data.has_bu && data.bu_date) {
            if (buDateBadge) {
                buDateBadge.classList.remove('hidden');
                buDateBadge.className = 'px-2.5 py-0.5 rounded-full text-xs font-bold bg-indigo-50 text-indigo-700 border border-indigo-200 flex items-center gap-1 shadow-xs';
            }
            if (buDateText) buDateText.textContent = `BU Permission: ${data.bu_date}`;
            if (buDateSub) buDateSub.textContent = data.bu_date;
        } else {
            if (buDateBadge) {
                buDateBadge.classList.remove('hidden');
                buDateBadge.className = 'px-2.5 py-0.5 rounded-full text-xs font-bold bg-slate-100 text-slate-600 border border-slate-200 flex items-center gap-1 shadow-xs';
            }
            if (buDateText) buDateText.textContent = 'Under Construction (No BU)';
            if (buDateSub) buDateSub.textContent = 'Under Construction (No BU)';
        }

        if (specsEl) {
            const m = data.unit_meta || {};
            const parts = [];
            if (m.block) parts.push(`Block: ${m.block}`);
            if (m.floor) parts.push(`Floor: ${m.floor}`);
            if (m.usage_type) parts.push(`Type: ${m.usage_type}`);
            if (m.size_sqft) parts.push(`Super: ${Number(m.size_sqft).toLocaleString('en-IN')} sqft`);
            if (m.carpet_sqft) parts.push(`Carpet: ${Number(m.carpet_sqft).toLocaleString('en-IN')} sqft`);
            specsEl.innerHTML = parts.length ? parts.map(p => `<span>${p}</span>`).join(' · ') : `<span>Unit ${data.unit_no}</span>`;
        }

        // Financial KPI Cards
        const sm = data.summary || {};
        const kpiReceipts = document.getElementById('unit-kpi-total-receipts');
        const kpiCount = document.getElementById('unit-kpi-count');
        const kpiTaxable = document.getElementById('unit-kpi-taxable-base');
        const kpiGst = document.getElementById('unit-kpi-total-gst');
        const kpiGstSplit = document.getElementById('unit-kpi-gst-split');
        const kpiExempt = document.getElementById('unit-kpi-exempt-passthrough');
        const kpiExemptSub = document.getElementById('unit-kpi-exempt-sub');

        if (kpiReceipts) kpiReceipts.textContent = '₹' + Number(sm.total_receipts || data.total_paid || 0).toLocaleString('en-IN', { maximumFractionDigits: 0 });
        if (kpiCount) kpiCount.textContent = `${sm.income_count || data.payment_count || 0} Member Receipts (${(data.vouchers || []).length} total records)`;
        if (kpiTaxable) kpiTaxable.textContent = '₹' + Number(sm.total_taxable_base || 0).toLocaleString('en-IN', { maximumFractionDigits: 0 });
        if (kpiGst) kpiGst.textContent = '₹' + Number(sm.total_tax || 0).toLocaleString('en-IN', { maximumFractionDigits: 0 });
        if (kpiGstSplit) kpiGstSplit.textContent = `CGST: ₹${Number(sm.total_cgst || 0).toLocaleString('en-IN', { maximumFractionDigits: 0 })} | SGST: ₹${Number(sm.total_sgst || 0).toLocaleString('en-IN', { maximumFractionDigits: 0 })}`;
        
        const exemptPassTotal = (sm.total_exempt || 0) + (sm.total_pass_through || 0);
        if (kpiExempt) kpiExempt.textContent = '₹' + Number(exemptPassTotal).toLocaleString('en-IN', { maximumFractionDigits: 0 });
        if (kpiExemptSub) kpiExemptSub.textContent = `Post-BU: ₹${Number(sm.total_exempt || 0).toLocaleString('en-IN', { maximumFractionDigits: 0 })} | Pass: ₹${Number(sm.total_pass_through || 0).toLocaleString('en-IN', { maximumFractionDigits: 0 })}`;

        // Owners Ribbon
        if (ownersBox) {
            ownersBox.innerHTML = (data.owners && data.owners.length)
                ? data.owners.map((o, i) => `<span class="px-2.5 py-1 rounded-full text-xs bg-blue-50 text-blue-700 border border-blue-200 font-semibold flex items-center gap-1.5"><span class="w-4 h-4 rounded-full bg-blue-600 text-white text-[10px] flex items-center justify-center font-bold">${i + 1}</span> ${o}</span>`).join('')
                : `<span class="text-xs text-slate-400 font-sans">No ownership records found for this unit.</span>`;
        }

        // Transfer / Cancelled Booking Notes
        if (notesBox) {
            let boxesHtml = '';
            if (data.cancelled_bookings && data.cancelled_bookings.length) {
                const cancelledTotalFmt = Number(data.cancelled_total || 0).toLocaleString('en-IN', { maximumFractionDigits: 0 });
                boxesHtml += `
                    <div class="rounded-xl bg-red-50 border border-red-200 px-3.5 py-2.5 mb-2">
                        <div class="flex items-center gap-1.5 text-red-800 text-xs font-bold mb-1">
                            <span class="material-symbols-outlined text-[16px]">cancel</span>
                            Cancelled / voided booking(s) — excluded from totals (₹${cancelledTotalFmt})
                        </div>
                        <div class="flex flex-col gap-1">
                            ${data.cancelled_bookings.map(b => `
                                <div class="text-xs text-red-900 font-sans">
                                    <span class="font-mono font-semibold line-through">${b.party_name || '—'}</span> ·
                                    <span class="font-mono">${b.date || '—'}</span> ·
                                    <span class="font-mono">${b.vch_no || '—'}</span> ·
                                    ₹${Number(b.amount || 0).toLocaleString('en-IN', { maximumFractionDigits: 0 })}
                                </div>
                            `).join('')}
                        </div>
                    </div>
                `;
            }
            if (data.transfer_notes && data.transfer_notes.length) {
                boxesHtml += `
                    <div class="rounded-xl bg-amber-50 border border-amber-200 px-3.5 py-2.5 mb-2">
                        <div class="flex items-center gap-1.5 text-amber-800 text-xs font-bold mb-1">
                            <span class="material-symbols-outlined text-[16px]">info</span>
                            Transfer / NOC / Resale remarks found in voucher narration
                        </div>
                        <div class="flex flex-col gap-1">
                            ${data.transfer_notes.map(n => `
                                <div class="text-xs text-amber-900 font-sans">
                                    <span class="font-mono font-semibold">${n.date || '—'}</span> ·
                                    <span class="font-mono">${n.vch_no || '—'}</span> ·
                                    ₹${Number(n.amount || 0).toLocaleString('en-IN', { maximumFractionDigits: 0 })} —
                                    <span class="italic">${n.narration || ''}</span>
                                </div>
                            `).join('')}
                        </div>
                    </div>
                `;
            }
            notesBox.innerHTML = boxesHtml;
        }

        // Store vouchers for in-modal search & render table
        currentUnitVouchersList = data.vouchers || [];
        if (vchCountBadge) vchCountBadge.textContent = currentUnitVouchersList.length;

        renderUnitVouchersTable(currentUnitVouchersList, data.project_key, data.bu_date);

        // Setup live search within modal
        if (searchInput) {
            searchInput.oninput = (e) => {
                const q = (e.target.value || '').toLowerCase().trim();
                if (!q) {
                    renderUnitVouchersTable(currentUnitVouchersList, data.project_key, data.bu_date);
                } else {
                    const filtered = currentUnitVouchersList.filter(v =>
                        (v.date || '').toLowerCase().includes(q) ||
                        (v.vch_no || '').toLowerCase().includes(q) ||
                        (v.party_name || '').toLowerCase().includes(q) ||
                        (v.narration || '').toLowerCase().includes(q) ||
                        (v.classification || '').toLowerCase().includes(q) ||
                        String(v.amount || '').includes(q)
                    );
                    renderUnitVouchersTable(filtered, data.project_key, data.bu_date);
                }
            };
        }

        // Ownership periods timeline (if resale/multiple owners)
        if (timeline) {
            const periods = data.ownership_periods || [];
            if (periods.length > 1) {
                timeline.innerHTML = `
                    <div class="text-xs font-bold text-slate-700 uppercase tracking-wider flex items-center gap-1 pt-2 border-t border-slate-200">
                        <span class="material-symbols-outlined text-[16px] text-blue-600">history_edu</span>
                        Ownership Transfer & Resale Timeline (${periods.length} Owners)
                    </div>
                    ${periods.map((p, idx) => {
                        const totalFmt = Number(p.total_paid || 0).toLocaleString('en-IN', { maximumFractionDigits: 0 });
                        const rangeText = p.start_date === p.end_date ? (p.start_date || '—') : `${p.start_date || '—'} → ${p.end_date || '—'}`;
                        return `
                            <div class="rounded-xl border border-slate-200 p-3 bg-slate-50 flex items-center justify-between flex-wrap gap-2 text-xs">
                                <div class="flex items-center gap-2">
                                    <span class="w-5 h-5 rounded-full bg-blue-600 text-white text-[10px] font-bold flex items-center justify-center">${p.sequence}</span>
                                    <span class="font-bold text-slate-900">${p.owner}</span>
                                    <span class="text-slate-500 font-mono text-[11px]">${rangeText}</span>
                                </div>
                                <div class="font-mono font-bold text-slate-700">
                                    ₹${totalFmt} <span class="text-slate-400 font-medium">(${p.payment_count} payments)</span>
                                </div>
                            </div>
                        `;
                    }).join('')}
                `;
            } else {
                timeline.innerHTML = '';
            }
        }

    } catch (err) {
        if (tableBody) tableBody.innerHTML = `<tr><td colspan="10" class="text-center py-6 text-red-500 font-sans">Error loading history: ${err.message}</td></tr>`;
    }
}

function renderUnitVouchersTable(vouchers, projectCode, buDateStr) {
    const tableBody = document.getElementById('unit-modal-table-body');
    if (!tableBody) return;

    if (!vouchers || vouchers.length === 0) {
        tableBody.innerHTML = `<tr><td colspan="10" class="text-center py-8 text-slate-400 font-sans">No vouchers found matching the filter</td></tr>`;
        return;
    }

    const parseDMY = (d) => {
        if (!d) return null;
        const p = String(d).split('-');
        if (p.length === 3) {
            if (p[0].length === 4) return new Date(parseInt(p[0]), parseInt(p[1]) - 1, parseInt(p[2]));
            return new Date(parseInt(p[2]), parseInt(p[1]) - 1, parseInt(p[0]));
        }
        return null;
    };
    const buDt = parseDMY(buDateStr);

    tableBody.innerHTML = vouchers.map((v, idx) => {
        let badgeHtml = '';
        if (v.badge_type === 'bu_review') {
            badgeHtml = `<span class="px-2 py-0.5 rounded text-xs bg-orange-500/10 text-orange-600 border border-orange-500/30 font-medium">⚠ ${v.classification}</span>`;
        } else if (v.badge_type === 'review') {
            badgeHtml = `<span class="px-2 py-0.5 rounded text-xs bg-red-500/10 text-red-600 border border-red-500/30 font-medium">⚠ ${v.classification}</span>`;
        } else if (v.badge_type === 'excluded_manual') {
            badgeHtml = `<span class="px-2 py-0.5 rounded text-xs bg-purple-500/10 text-purple-600 border border-purple-500/30 font-medium">✎ ${v.classification}</span>`;
        } else if (v.badge_type === 'pass_through') {
            badgeHtml = `<span class="px-2 py-0.5 rounded text-xs bg-sky-500/10 text-sky-600 border border-sky-500/30 font-medium">${v.classification}</span>`;
        } else if (v.badge_type === 'creditor' || v.badge_type === 'expense') {
            badgeHtml = `<span class="px-2 py-0.5 rounded text-xs bg-slate-400/10 text-slate-500 border border-slate-400/30 font-medium">${v.classification}</span>`;
        } else if (v.badge_type === 'cancelled') {
            badgeHtml = `<span class="px-2 py-0.5 rounded text-xs bg-red-400/10 text-red-500 border border-red-400/30 font-medium line-through">${v.classification}</span>`;
        } else if (v.badge_type === 'exempt' || (v.classification && v.classification.toLowerCase().includes('exempt'))) {
            badgeHtml = `<span class="px-2 py-0.5 rounded text-xs bg-secondary/10 text-secondary border border-secondary/30 font-medium">${v.classification}</span>`;
        } else if (v.badge_type === 'taxable-5' || (v.classification && v.classification.includes('5%'))) {
            badgeHtml = `<span class="px-2 py-0.5 rounded text-xs bg-amber-500/10 text-amber-500 border border-amber-500/30 font-medium">${v.classification}</span>`;
        } else if (v.badge_type === 'taxable-1' || (v.classification && v.classification.includes('1%'))) {
            badgeHtml = `<span class="px-2 py-0.5 rounded text-xs bg-primary/10 text-primary border border-primary/30 font-medium">${v.classification}</span>`;
        } else {
            badgeHtml = `<span class="px-2 py-0.5 rounded text-xs bg-surface-container text-on-surface border border-outline-variant font-medium">${v.classification}</span>`;
        }

        const vDt = parseDMY(v.date);
        let buTagHtml = '';
        if (buDt && vDt) {
            if (vDt >= buDt) {
                buTagHtml = `<div class="text-[10.5px] text-emerald-700 font-bold flex items-center gap-1 mt-0.5" title="Payment on ${v.date} received AFTER BU Permission (${buDateStr})"><span class="w-1.5 h-1.5 rounded-full bg-emerald-500 inline-block"></span>Post-BU</div>`;
            } else {
                buTagHtml = `<div class="text-[10.5px] text-amber-700 font-bold flex items-center gap-1 mt-0.5" title="Payment on ${v.date} received BEFORE BU Permission (${buDateStr})"><span class="w-1.5 h-1.5 rounded-full bg-amber-500 inline-block"></span>Pre-BU</div>`;
            }
        }

        const amtFmt = Number(v.amount || 0).toLocaleString('en-IN', { maximumFractionDigits: 0 });
        const taxBaseFmt = Number(v.taxable_amount || 0).toLocaleString('en-IN', { maximumFractionDigits: 0 });
        const gstFmt = Number(v.total_tax || 0).toLocaleString('en-IN', { maximumFractionDigits: 0 });
        const pencilClass = v.has_override ? 'text-blue-600' : 'text-slate-300 hover:text-slate-500';

        return `
            <tr class="hover:bg-slate-50/80 transition-colors">
                <td class="py-2.5 px-3 text-on-surface">
                    <div class="font-mono font-medium">${v.date || '—'}</div>
                    ${buTagHtml}
                </td>
                <td class="py-2.5 px-3 text-primary font-bold font-mono">${v.vch_no || '—'}</td>
                <td class="py-2.5 px-3 font-sans text-xs text-on-surface-variant font-medium">${v.type || 'Receipt'}</td>
                <td class="py-2.5 px-4 font-sans text-on-surface font-medium">${v.party_name || '—'}</td>
                <td class="py-2.5 px-3 text-right text-on-surface font-bold font-mono">₹${amtFmt}</td>
                <td class="py-2.5 px-3 text-right text-blue-700 font-semibold font-mono">₹${taxBaseFmt}</td>
                <td class="py-2.5 px-3 text-right text-emerald-700 font-semibold font-mono">₹${gstFmt}</td>
                <td class="py-2.5 px-3 font-sans">${badgeHtml}</td>
                <td class="py-2.5 px-3 font-sans text-[11px] text-on-surface-variant max-w-xs truncate" title="${(v.narration || '').replace(/"/g, '&quot;')}">${v.narration || '—'}</td>
                <td class="py-2.5 px-2 text-center">
                    <button type="button" data-index="${idx}" class="btn-unit-modal-edit p-1 rounded hover:bg-slate-200 transition-colors ${pencilClass}" title="Edit classification">
                        <span class="material-symbols-outlined text-[16px]">edit</span>
                    </button>
                </td>
            </tr>
        `;
    }).join('');

    // Attach edit button listeners inside unit modal
    const editButtons = tableBody.querySelectorAll('.btn-unit-modal-edit');
    editButtons.forEach(btn => {
        const idx = parseInt(btn.getAttribute('data-index'), 10);
        const v = vouchers[idx];
        if (v) {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                openOverrideModal({
                    ...v,
                    cr_amount: v.amount,
                    flat_no: currentActiveUnitModal ? currentActiveUnitModal.unitNo : '',
                    project: projectCode
                });
            });
        }
    });
}

let currentOverrideVoucher = null;

function openOverrideModal(v) {
    currentOverrideVoucher = v;
    const modal = document.getElementById('voucher-override-modal');
    const subtitle = document.getElementById('override-modal-subtitle');
    const autoBox = document.getElementById('override-auto-detected');
    const isIncomeSel = document.getElementById('override-is-income');
    const buStatusSel = document.getElementById('override-bu-status');
    const rateSel = document.getElementById('override-rate');
    const noteInput = document.getElementById('override-note');

    const unitLabel = (v.flat_no && v.flat_no !== 'undefined') ? v.flat_no : (v.unit || '—');
    const memberLabel = (v.member_name && v.member_name !== 'undefined') ? v.member_name : (v.name || 'Member');
    if (subtitle) subtitle.textContent = `Vch ${v.vch_no} · ${v.date} · ${unitLabel} · ${memberLabel}`;
    if (autoBox) autoBox.innerHTML = `<span class="font-bold">Auto-detected:</span> ${v.classification}`;

    if (isIncomeSel) isIncomeSel.value = v.override_is_income === true ? 'true' : (v.override_is_income === false ? 'false' : 'auto');
    if (buStatusSel) buStatusSel.value = v.override_bu_status || 'auto';
    if (rateSel) rateSel.value = v.override_rate ? String(v.override_rate) : 'auto';
    if (noteInput) noteInput.value = v.override_note || '';

    if (modal) modal.classList.remove('hidden');
}

function closeOverrideModal() {
    const modal = document.getElementById('voucher-override-modal');
    if (modal) modal.classList.add('hidden');
    currentOverrideVoucher = null;
}

async function saveVoucherOverride(clearAll) {
    if (!currentOverrideVoucher) return;
    const v = currentOverrideVoucher;
    const projectSel = document.getElementById('select-voucher-project');
    const projectCode = projectSel ? projectSel.value : '010010';

    const isIncomeSel = document.getElementById('override-is-income');
    const buStatusSel = document.getElementById('override-bu-status');
    const rateSel = document.getElementById('override-rate');
    const noteInput = document.getElementById('override-note');

    const payload = {
        project: projectCode,
        vch_no: v.vch_no,
        date: v.date,
        bu_status: clearAll ? 'auto' : (buStatusSel ? buStatusSel.value : 'auto'),
        rate: clearAll ? null : ((rateSel && rateSel.value !== 'auto') ? parseFloat(rateSel.value) : null),
        note: clearAll ? '' : (noteInput ? noteInput.value.trim() : '')
    };
    if (!clearAll && isIncomeSel && isIncomeSel.value !== 'auto') {
        payload.is_income = isIncomeSel.value === 'true';
    }

    const saveBtn = document.getElementById('btn-save-override');
    const origText = saveBtn ? saveBtn.textContent : '';
    if (saveBtn) { saveBtn.disabled = true; saveBtn.textContent = 'Saving...'; }

    try {
        const resp = await fetch('/api/vouchers/override', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const data = await resp.json();
        if (data.status !== 'success') {
            alert('Could not save: ' + (data.message || 'Unknown error'));
            return;
        }
        closeOverrideModal();
        await loadRealVouchers(projectCode);
        if (currentActiveUnitModal) {
            await openUnitHistory(currentActiveUnitModal.projectKey, currentActiveUnitModal.unitNo);
        }
    } catch (err) {
        alert('Network error saving override: ' + err.message);
    } finally {
        if (saveBtn) { saveBtn.disabled = false; saveBtn.textContent = origText; }
    }
}

document.addEventListener('DOMContentLoaded', () => {
    checkStatus();
    setInterval(checkStatus, 8000);
    updateVoucherCategoryButtons();
    loadRealVouchers();

    // Income / All Vouchers category toggle
    document.querySelectorAll('.voucher-category-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const cat = btn.getAttribute('data-category');
            if (cat === currentVoucherCategory) return;
            currentVoucherCategory = cat;
            updateVoucherCategoryButtons();
            loadRealVouchers();
            appendLog('INFO', `Switched voucher view to: ${cat === 'income' ? 'Income Vouchers (flat/shop payments)' : 'All Vouchers (incl. purchases)'}.`);
        });
    });

    // Setup Project Selector Dropdowns (Header & Voucher Tab)
    const vProjectSelect = document.getElementById('select-voucher-project');
    const hProjectSelect = document.getElementById('select-header-project');

    if (vProjectSelect) {
        vProjectSelect.addEventListener('change', (e) => {
            const val = e.target.value;
            if (hProjectSelect) hProjectSelect.value = val;
            loadRealVouchers(val);
            appendLog('INFO', `Switched project view to ${val}.`);
        });
    }

    if (hProjectSelect) {
        hProjectSelect.addEventListener('change', (e) => {
            const val = e.target.value;
            if (vProjectSelect) vProjectSelect.value = val;
            loadRealVouchers(val);
            appendLog('INFO', `Switched project view to ${val}.`);
        });
    }

    // Setup Month and Year Filter Dropdowns
    const vMonthSelect = document.getElementById('select-voucher-month');
    const vYearSelect = document.getElementById('select-voucher-year');
    const gstr1MonthSelect = document.getElementById('select-month');

    function formatINR(val) {
        const num = Number(val || 0);
        return num.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    }

    function updateStatutoryMonthLabels(cleanMonth) {
        const m = cleanMonth || 'SEP-26';
        const ids = ['statutory-mappings-month', 'statutory-output-tax-month', 'portfolio-aggregate-month'];
        ids.forEach(id => {
            const el = document.getElementById(id);
            if (el) el.textContent = m;
        });
    }

    function updateStatutoryCardUI(monthStr, summary) {
        const cleanMonth = (monthStr || 'SEP-26').split(' ')[0].toUpperCase();
        updateStatutoryMonthLabels(cleanMonth);

        if (!summary) return;

        // Overview Tab - Statutory GSTR-1 Return Mappings card
        const t4Taxable = document.getElementById('statutory-table4-taxable');
        const t4Tax = document.getElementById('statutory-table4-tax');
        const t7Taxable = document.getElementById('statutory-table7-taxable');
        const t7Tax = document.getElementById('statutory-table7-tax');
        const t11Gross = document.getElementById('statutory-table11-gross');
        const t11Tax = document.getElementById('statutory-table11-tax');
        const totalLiab = document.getElementById('statutory-total-liability');

        if (t4Taxable) t4Taxable.textContent = '₹' + formatINR(summary.table_4_b2b?.taxable || 0);
        if (t4Tax) t4Tax.textContent = '₹' + formatINR(summary.table_4_b2b?.tax || 0);
        if (t7Taxable) t7Taxable.textContent = '₹' + formatINR(summary.table_7_b2c?.taxable ?? summary.net_taxable ?? 0);
        if (t7Tax) t7Tax.textContent = '₹' + formatINR(summary.table_7_b2c?.tax ?? summary.output_gst ?? 0);
        if (t11Gross) t11Gross.textContent = '₹' + formatINR(summary.table_11_advances?.gross ?? summary.gross_receipts ?? 0);
        if (t11Tax) t11Tax.textContent = '₹' + formatINR(summary.table_11_advances?.net_tax ?? summary.output_gst ?? 0);
        if (totalLiab) totalLiab.textContent = '₹' + formatINR(summary.total_tax_liability ?? summary.output_gst ?? 0);

        // Tab 5 - GSTR-1 & 3B Returns tab
        const retT4Taxable = document.getElementById('tab-returns-table4-taxable');
        const retT4Tax = document.getElementById('tab-returns-table4-tax');
        const retT7Taxable = document.getElementById('tab-returns-table7-taxable');
        const retT7Tax = document.getElementById('tab-returns-table7-tax');
        const retT8Exempt = document.getElementById('tab-returns-table8-exempt');
        const retT11Gross = document.getElementById('tab-returns-table11-gross');
        const retT11Tax = document.getElementById('tab-returns-table11-tax');

        if (retT4Taxable) retT4Taxable.textContent = '₹' + formatINR(summary.table_4_b2b?.taxable || 0);
        if (retT4Tax) retT4Tax.textContent = '₹' + formatINR(summary.table_4_b2b?.tax || 0);
        if (retT7Taxable) retT7Taxable.textContent = '₹' + formatINR(summary.table_7_b2c?.taxable ?? summary.net_taxable ?? 0);
        if (retT7Tax) retT7Tax.textContent = '₹' + formatINR(summary.table_7_b2c?.tax ?? summary.output_gst ?? 0);
        if (retT8Exempt) retT8Exempt.textContent = '₹' + formatINR(summary.exempt_post_bu || 0);
        if (retT11Gross) retT11Gross.textContent = '₹' + formatINR(summary.table_11_advances?.gross ?? summary.gross_receipts ?? 0);
        if (retT11Tax) retT11Tax.textContent = '₹' + formatINR(summary.table_11_advances?.net_tax ?? summary.output_gst ?? 0);
    }

    async function fetchAndRenderStatutorySummary(monthStr) {
        const cleanMonth = (monthStr || 'SEP-26').split(' ')[0].toUpperCase();
        updateStatutoryMonthLabels(cleanMonth);
        try {
            const resp = await fetch(`/api/gstr1/summary?month=${encodeURIComponent(cleanMonth)}`);
            const res = await resp.json();
            if (res.status === 'success' && res.summary) {
                updateStatutoryCardUI(cleanMonth, res.summary);
            }
        } catch (err) {
            console.warn('[Statutory Summary Fetch Failed]', err);
        }
    }

    function syncMonthSelections(sourceValue) {
        const clean = (sourceValue || 'SEP-26').split(' ')[0].toUpperCase();
        currentDownloadUrl = `/api/download/GSTR-1_${clean}_AUTOMATED.xlsx`;
        
        const parts = clean.split('-');
        const mPart = parts[0];
        const yPart = parts.length > 1 ? (parts[1].length === 2 ? '20' + parts[1] : parts[1]) : '2026';
        
        if (vMonthSelect && vMonthSelect.value !== mPart) {
            vMonthSelect.value = mPart;
        }
        if (vYearSelect && vYearSelect.value !== yPart) {
            vYearSelect.value = yPart;
        }
        if (gstr1MonthSelect) {
            for (let opt of gstr1MonthSelect.options) {
                if (opt.value.startsWith(clean)) {
                    gstr1MonthSelect.value = opt.value;
                    break;
                }
            }
        }
        updateStatutoryMonthLabels(clean);
        fetchAndRenderStatutorySummary(clean);
    }

    if (gstr1MonthSelect) {
        // Set initial download url from current select-month
        const initM = gstr1MonthSelect.value.split(' ')[0];
        currentDownloadUrl = `/api/download/GSTR-1_${initM}_AUTOMATED.xlsx`;
        updateStatutoryMonthLabels(initM);
        fetchAndRenderStatutorySummary(initM);

        gstr1MonthSelect.addEventListener('change', (e) => {
            const mVal = e.target.value.split(' ')[0];
            syncMonthSelections(mVal);
            loadRealVouchers();
            appendLog('INFO', `Switched GSTR-1 return filing month to ${mVal}. Download URL ready.`);
        });
    }

    if (vMonthSelect) {
        vMonthSelect.addEventListener('change', (e) => {
            const mVal = e.target.value;
            const yVal = vYearSelect ? vYearSelect.value.slice(-2) : '26';
            if (mVal && mVal !== 'ALL') {
                syncMonthSelections(`${mVal}-${yVal}`);
            }
            loadRealVouchers();
            appendLog('INFO', `Filtered vouchers by month: ${mVal}.`);
        });
    }

    if (vYearSelect) {
        vYearSelect.addEventListener('change', (e) => {
            const yVal = e.target.value;
            loadRealVouchers();
            appendLog('INFO', `Filtered vouchers by year: ${yVal}.`);
        });
    }

    // 1. Setup Tab Switching Listeners
    document.querySelectorAll('.nav-tab, .top-nav-tab').forEach(tabElem => {
        tabElem.addEventListener('click', (e) => {
            e.preventDefault();
            const tabName = tabElem.getAttribute('data-tab');
            if (tabName) {
                switchTab(tabName);
            }
        });
    });

    // 2. Hash Routing
    window.addEventListener('hashchange', () => {
        const hash = window.location.hash.replace('#', '') || 'overview';
        switchTab(hash);
    });

    // Initial Tab resolution from URL hash
    const initialHash = window.location.hash.replace('#', '') || 'overview';
    switchTab(initialHash);

    // 3. Process Active Vouchers Button (Sidebar Header)
    const btnProcessVouchers = document.getElementById('btn-process-vouchers');
    if (btnProcessVouchers) {
        btnProcessVouchers.addEventListener('click', () => {
            switchTab('overview');
            const vHub = document.getElementById('voucher-hub-section');
            if (vHub) {
                vHub.scrollIntoView({ behavior: 'smooth' });
            }
            appendLog('INFO', 'Navigated to Tally Voucher Ingestion & Extraction hub in the center of Overview.');
        });
    }

    // 4. Generation Button Handlers (Any button with generate class or text)
    const handleGenerate = async (btn) => {
        btn.disabled = true;
        btn.style.opacity = '0.7';
        const origHtml = btn.innerHTML;
        btn.innerHTML = `<span class="material-symbols-outlined text-[20px] animate-spin">sync</span><span>Compiling Vouchers...</span>`;

        const selMonth = document.getElementById('select-month');
        const month = selMonth ? selMonth.value.split(' ')[0] : 'SEP-26';

        // Dynamically compute date range from selected month
        const monthNumMap = {'JAN':'01','FEB':'02','MAR':'03','APR':'04','MAY':'05','JUN':'06','JUL':'07','AUG':'08','SEP':'09','OCT':'10','NOV':'11','DEC':'12'};
        const [mCode, yCode] = month.split('-');
        const mNum = monthNumMap[mCode.toUpperCase()] || '09';
        const fullYear = yCode ? (yCode.length === 2 ? '20' + yCode : yCode) : '2026';
        const daysInMonth = new Date(parseInt(fullYear), parseInt(mNum), 0).getDate();
        const fromDate = `${fullYear}-${mNum}-01`;
        const toDate = `${fullYear}-${mNum}-${String(daysInMonth).padStart(2, '0')}`;

        appendLog('INFO', `⚡ Compiling GSTR-1 for ${month} (${fromDate} to ${toDate}) via Flask REST API...`);

        try {
            const resp = await fetch('/api/generate', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ month: month, from_date: fromDate, to_date: toDate })
            });
            const res = await resp.json();
            if (res.status === 'success') {
                currentDownloadUrl = res.download_url;
                if (res.logs) {
                    res.logs.forEach(l => appendLog('INFO', l));
                }
                appendLog('SUCCESS', `Successfully compiled 23-sheet GSTR-1 workbook for ${res.month}: ${res.filename}`);
                if (res.summary) {
                    updateStatutoryCardUI(res.month || month, res.summary);
                    const grossCr = (Number(res.summary.gross_receipts || 0) / 10000000).toFixed(2);
                    const exemptCr = (Number(res.summary.exempt_post_bu || 0) / 10000000).toFixed(2);
                    const netTaxableCr = (Number(res.summary.net_taxable || 0) / 10000000).toFixed(2);
                    appendLog('READY', `Gross Collections: ₹${grossCr} Cr | Post-BU Exempt: ₹${exemptCr} Cr | Net Taxable: ₹${netTaxableCr} Cr`);
                    appendLog('READY', `${res.summary.total_units} Active Member Units verified. Initiating direct file download.`);
                }

                loadActivityLogs();

                // Direct file download trigger
                window.location.href = currentDownloadUrl;
            } else {
                appendLog('ERROR', `Generation error: ${res.message}`);
            }
        } catch (err) {
            appendLog('ERROR', `Network / API error: ${err.message}`);
        } finally {
            btn.disabled = false;
            btn.style.opacity = '1';
            btn.innerHTML = origHtml;
        }
    };

    document.querySelectorAll('.btn-generate-gstr1').forEach(btn => {
        btn.addEventListener('click', () => handleGenerate(btn));
    });

    // 5. Download Button Handlers
    document.querySelectorAll('.btn-download-xlsx').forEach(btn => {
        btn.addEventListener('click', () => {
            const selMonth = document.getElementById('select-month');
            const targetMonth = selMonth ? selMonth.value.split(' ')[0] : 'SEP-26';
            const dlUrl = `/api/download/GSTR-1_${targetMonth}_AUTOMATED.xlsx`;
            appendLog('INFO', `Downloading GSTR-1 Excel file for ${targetMonth}: ${dlUrl}`);
            window.location.href = dlUrl;
        });
    });

    // 6. Resync & Tally Handlers
    document.querySelectorAll('.btn-resync-ledger').forEach(btn => {
        btn.addEventListener('click', async () => {
            await executeTallyLiveSync(btn);
        });
    });

    // 7. Interactive Table Search / Filters
    const projectSearch = document.getElementById('project-search-input');
    if (projectSearch) {
        projectSearch.addEventListener('input', (e) => {
            const query = e.target.value.toLowerCase();
            document.querySelectorAll('#project-table-body tr').forEach(row => {
                const text = row.innerText.toLowerCase();
                row.style.display = text.includes(query) ? '' : 'none';
            });
        });
    }

    const voucherSearch = document.getElementById('voucher-search-input');
    if (voucherSearch) {
        voucherSearch.addEventListener('input', (e) => {
            const query = e.target.value.toLowerCase();
            document.querySelectorAll('#voucher-table-body tr').forEach(row => {
                const text = row.innerText.toLowerCase();
                row.style.display = text.includes(query) ? '' : 'none';
            });
        });
    }

    // 8. Button-Based Live Sync with Tally Port 9000 & Comprehensive Audit Details Modal
    let currentModalVouchers = [];
    let currentModalDuplicatesPrevented = 0;

    function renderModalTable(vouchers) {
        const tbody = document.getElementById('modal-vouchers-tbody');
        const countBadge = document.getElementById('modal-table-count');
        if (!tbody) return;

        tbody.innerHTML = '';
        if (!vouchers || vouchers.length === 0) {
            tbody.innerHTML = `<tr><td colspan="9" class="text-center py-8 text-slate-400 font-sans">
                <div class="flex flex-col items-center justify-center gap-1.5">
                    <span class="material-symbols-outlined text-[28px] text-slate-300">receipt_long</span>
                    <span class="font-bold text-slate-600">No Vouchers Match Search Criteria</span>
                    <span class="text-xs text-slate-400">Clear your search input to view all authentic vouchers.</span>
                </div>
            </td></tr>`;
            if (countBadge) countBadge.textContent = 'Showing 0 Vouchers';
            return;
        }

        if (countBadge) {
            countBadge.textContent = `Showing All ${vouchers.length.toLocaleString('en-IN')} Authentic Vouchers (${currentModalDuplicatesPrevented.toLocaleString('en-IN')} Duplicates Prevented)`;
        }

        const fragment = document.createDocumentFragment();
        vouchers.forEach((v, idx) => {
            const tr = document.createElement('tr');
            tr.className = 'hover:bg-slate-50 transition-colors';

            let badgeHtml = '';
            const cls = (v.classification || '').toLowerCase();
            if (v.badge_type === 'exempt' || cls.includes('exempt')) {
                badgeHtml = `<span class="px-2 py-0.5 rounded text-[10px] bg-emerald-50 text-emerald-700 border border-emerald-200 font-bold">${v.classification || '100% Exempt (Post-BU)'}</span>`;
            } else if (v.badge_type === 'taxable-1' || cls.includes('1%')) {
                badgeHtml = `<span class="px-2 py-0.5 rounded text-[10px] bg-blue-50 text-blue-700 border border-blue-200 font-bold">${v.classification || '1% Affordable'}</span>`;
            } else if (v.badge_type === 'taxable-5' || cls.includes('5%')) {
                badgeHtml = `<span class="px-2 py-0.5 rounded text-[10px] bg-amber-50 text-amber-800 border border-amber-200 font-bold">${v.classification || '5% Standard'}</span>`;
            } else {
                badgeHtml = `<span class="px-2 py-0.5 rounded text-[10px] bg-slate-100 text-slate-700 border border-slate-200 font-bold">${v.classification || 'GST Taxable'}</span>`;
            }

            const crAmt = Number(v.cr_amount || v.amount || 0);
            const dedAmt = Number(v.deductions || 0);
            const taxAmt = Number(v.taxable_amount || 0);

            const vchNum = v.vch_no || v.voucher_number || `VCH-${idx + 1}`;
            const unitDisp = (v.flat_no && v.flat_no !== 'undefined') ? v.flat_no : ((v.unit && v.unit !== 'undefined') ? v.unit : '—');
            const partyDisp = v.member_name || v.name || 'Member';

            tr.innerHTML = `
                <td class="py-2.5 px-3 text-slate-700 font-mono text-[11px]">${v.date || '—'}</td>
                <td class="py-2.5 px-3 text-blue-700 font-bold font-mono text-[11px]">${vchNum}</td>
                <td class="py-2.5 px-3 text-slate-600 font-sans text-[11px]">${v.project || 'Sun Builders'}</td>
                <td class="py-2.5 px-3 font-mono font-bold text-blue-900 bg-blue-50/60 px-2 py-0.5 rounded text-[11px]">${unitDisp}</td>
                <td class="py-2.5 px-4 font-sans text-slate-900 font-medium text-[11px]">${partyDisp}</td>
                <td class="py-2.5 px-3 text-right text-slate-900 font-semibold font-mono text-[11px]">₹${crAmt.toLocaleString('en-IN', { maximumFractionDigits: 0 })}</td>
                <td class="py-2.5 px-3 text-right text-emerald-700 font-medium font-mono text-[11px]">₹${dedAmt.toLocaleString('en-IN', { maximumFractionDigits: 0 })}</td>
                <td class="py-2.5 px-3 text-right text-blue-700 font-bold font-mono text-[11px]">₹${taxAmt.toLocaleString('en-IN', { maximumFractionDigits: 0 })}</td>
                <td class="py-2.5 px-4 font-sans">${badgeHtml}</td>
            `;
            fragment.appendChild(tr);
        });
        tbody.appendChild(fragment);
    }

    function addModalLog(msg, level = 'INFO') {
        const termLogs = document.getElementById('modal-terminal-logs');
        const termWrap = document.getElementById('modal-terminal-wrapper');
        if (!termLogs) return;
        const now = new Date();
        const timeStr = now.toTimeString().split(' ')[0];
        const color = level === 'ERROR' ? 'text-red-400' : (level === 'SUCCESS' ? 'text-emerald-300 font-bold' : (level === 'WARN' ? 'text-amber-300' : 'text-slate-300'));
        const div = document.createElement('div');
        div.className = `${color} text-[11px] leading-relaxed`;
        div.textContent = `[${timeStr}] [${level}] ${msg}`;
        termLogs.appendChild(div);
        if (termWrap) termWrap.scrollTop = termWrap.scrollHeight;
    }

    function setModalPipelineStage(stepNum, title, pct) {
        const stageText = document.getElementById('modal-stage-text');
        const progPct = document.getElementById('modal-progress-pct');
        const progBar = document.getElementById('modal-progress-bar');
        const stageIcon = document.getElementById('modal-stage-icon');

        if (stageText) stageText.textContent = `Background Activity: ${title}`;
        if (progPct) progPct.textContent = `${pct}%`;
        if (progBar) progBar.style.width = `${pct}%`;

        if (stageIcon) {
            if (pct >= 100) {
                stageIcon.className = "material-symbols-outlined text-[18px] text-emerald-600";
                stageIcon.textContent = "check_circle";
            } else {
                stageIcon.className = "material-symbols-outlined text-[18px] text-blue-600 animate-spin";
                stageIcon.textContent = "sync";
            }
        }

        // Update step pills
        for (let i = 1; i <= 4; i++) {
            const stepEl = document.getElementById(`step-pipe-${i}`);
            if (stepEl) {
                const icon = stepEl.querySelector('.material-symbols-outlined');
                if (i < stepNum) {
                    stepEl.className = "flex items-center gap-1.5 p-1.5 rounded-lg bg-emerald-50 border border-emerald-200 text-emerald-800 font-bold";
                    if (icon) {
                        icon.className = "material-symbols-outlined text-[15px] text-emerald-600";
                        icon.textContent = "check_circle";
                    }
                } else if (i === stepNum) {
                    stepEl.className = "flex items-center gap-1.5 p-1.5 rounded-lg bg-blue-50 border border-blue-300 text-blue-800 font-bold ring-1 ring-blue-400";
                    if (icon) {
                        icon.className = "material-symbols-outlined text-[15px] text-blue-600 animate-spin";
                        icon.textContent = "sync";
                    }
                } else {
                    stepEl.className = "flex items-center gap-1.5 p-1.5 rounded-lg bg-white border border-slate-200 text-slate-400";
                    if (icon) {
                        icon.className = "material-symbols-outlined text-[15px] text-slate-300";
                        icon.textContent = "radio_button_unchecked";
                    }
                }
            }
        }
    }

    async function executeTallyLiveSync(triggerBtn) {
        let originalContent = '';
        if (triggerBtn) {
            originalContent = triggerBtn.innerHTML;
            triggerBtn.disabled = true;
            triggerBtn.innerHTML = `<span class="material-symbols-outlined text-[18px] animate-spin">sync</span><span>Syncing Tally (9000)...</span>`;
        }

        const syncModal = document.getElementById('sync-agent-modal');
        if (syncModal) {
            syncModal.classList.remove('hidden');
        }

        const modalTbody = document.getElementById('modal-vouchers-tbody');
        if (modalTbody) {
            modalTbody.innerHTML = `<tr><td colspan="9" class="text-center py-12 text-slate-600 font-sans">
                <div class="flex flex-col items-center justify-center gap-3">
                    <span class="material-symbols-outlined text-[36px] animate-spin text-blue-600">sync</span>
                    <span class="font-bold text-slate-800 text-sm">Connecting directly to Tally on Port 9000...</span>
                    <span class="text-xs text-slate-500">Extracting authentic full daybook dump &amp; enforcing 100% zero-duplicate prevention...</span>
                </div>
            </td></tr>`;
        }

        const termLogs = document.getElementById('modal-terminal-logs');
        if (termLogs) termLogs.innerHTML = '';

        setModalPipelineStage(1, "Handshaking Port 9000 XML Socket...", 20);
        addModalLog("Connecting to Tally socket http://localhost:9000...", "INFO");
        appendLog('INFO', '⚡ Initiating live Tally voucher ingestion on Port 9000...');

        try {
            let data = null;
            const vProjSelect = document.getElementById('select-voucher-project');
            const targetProjCode = (vProjSelect && vProjSelect.value && vProjSelect.value !== '010010') ? vProjSelect.value : null;

            // On Railway Cloud, the browser can't call a PC's localhost directly (Chrome
            // blocks an HTTPS page silently calling plain HTTP localhost). Instead, queue
            // the request on the cloud and let the local agent (python server.py running
            // on the PC where Tally is open) pick it up and report back.
            if (window.location.hostname.includes('railway.app')) {
                addModalLog("Railway Cloud session detected. Queuing sync request for your local Tally agent...", "INFO");
                try {
                    const reqResp = await fetch('/api/tally/request_sync', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ project_code: targetProjCode })
                    });
                    const reqData = await reqResp.json();
                    const requestId = reqData.request_id;
                    addModalLog(`Request queued. Waiting for your local Tally agent to pick it up (make sure "Start_Tally_Agent.bat" is running on the Tally PC)...`, "INFO");

                    const maxAttempts = 150; // ~10 minutes at 4s intervals
                    for (let attempt = 0; attempt < maxAttempts; attempt++) {
                        await new Promise(r => setTimeout(r, 4000));
                        const pollResp = await fetch(`/api/tally/sync_result/${requestId}`);
                        const pollData = await pollResp.json();
                        if (pollData.status === 'done') {
                            data = pollData.result;
                            addModalLog("Local agent responded with live Tally data!", "SUCCESS");
                            break;
                        }
                    }
                    if (!data) {
                        data = {
                            status: 'offline',
                            connected: false,
                            is_cloud: true,
                            message: 'No response from your local Sun Builders app within 10 minutes. Make sure "python server.py" is running on the PC where Tally is open, and that PC has internet access.',
                            company: null,
                            count: 0,
                            vouchers: []
                        };
                    }
                } catch (_e) {
                    addModalLog("Could not reach the cloud sync queue. Checking server directly...", "WARN");
                }
            }

            if (!data) {
                const resp = await fetch('/api/tally/sync_live', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ project_code: targetProjCode })
                });
                data = await resp.json();
            }

            if (!data.connected || data.status === 'offline') {
                setModalPipelineStage(1, "Port 9000 Disconnected (Tally is Closed)", 0);
                addModalLog(`[OFFLINE] ${data.message || 'Port 9000 is closed or Tally Prime is not running.'}`, "ERROR");
                addModalLog("Please ensure Tally Prime is open on this computer and your company is loaded.", "WARN");

                const connBadgeText = document.getElementById('modal-conn-text');
                if (connBadgeText) {
                    connBadgeText.textContent = 'Port 9000 OFFLINE';
                    if (connBadgeText.parentElement) {
                        connBadgeText.parentElement.className = 'px-2.5 py-0.5 rounded-full text-xs font-semibold bg-red-50 text-red-700 border border-red-200 inline-flex items-center gap-1';
                    }
                }

                const step1 = document.getElementById('step-pipe-1');
                if (step1) {
                    step1.className = "flex items-center gap-1.5 p-1.5 rounded-lg bg-red-50 border border-red-200 text-red-700 font-bold";
                    step1.innerHTML = `<span class="material-symbols-outlined text-[15px] text-red-600">cancel</span><span class="truncate">1. Port 9000 Disconnected</span>`;
                }

                if (modalTbody) {
                    modalTbody.innerHTML = `<tr><td colspan="9" class="text-center py-12 text-slate-700 font-sans">
                        <div class="flex flex-col items-center justify-center gap-2.5">
                            <span class="material-symbols-outlined text-[42px] text-red-500">wifi_off</span>
                            <span class="font-bold text-base text-slate-900">Tally Prime is Closed or Port 9000 is Offline</span>
                            <span class="text-xs text-slate-500 max-w-lg">
                                ${data.message || 'No connection on http://localhost:9000.'}<br/>
                                <strong class="text-slate-800">How to sync:</strong> 1. Open Tally Prime on this PC. 2. Open your project company (e.g. Gravitas). 3. Click "Re-Sync Tally (9000)".
                            </span>
                        </div>
                    </td></tr>`;
                }
                return;
            }

            if (data.status === 'warning') {
                setModalPipelineStage(2, "Tally Online: Please Open Company", 40);
                addModalLog(`[WARNING] ${data.message}`, "WARN");
                if (modalTbody) {
                    modalTbody.innerHTML = `<tr><td colspan="9" class="text-center py-12 text-amber-700 font-sans">
                        <div class="flex flex-col items-center justify-center gap-2">
                            <span class="material-symbols-outlined text-[36px] text-amber-500">folder_open</span>
                            <span class="font-bold text-base text-slate-800">No Company is Currently Open in Tally</span>
                            <span class="text-xs text-slate-500 max-w-md">Port 9000 is active, but you must open your company inside Tally Prime first.</span>
                        </div>
                    </td></tr>`;
                }
                return;
            }

            if (data.status === 'success') {
                const totalCount = data.count || 0;
                const duplicatesPrevented = data.duplicates_prevented ?? data.unchanged ?? 0;
                currentModalDuplicatesPrevented = duplicatesPrevented;
                setModalPipelineStage(2, `Identified Active Company: ${data.company}`, 50);
                addModalLog(`Identified Active Company in Tally: ${data.company}`, "INFO");

                setModalPipelineStage(3, `Streaming Full Daybook (${totalCount} Vouchers)...`, 75);
                addModalLog(`Extracted ${totalCount} authentic vouchers from Tally Daybook collection...`, "INFO");

                setModalPipelineStage(4, `Executing Deduplication & Verification (${duplicatesPrevented.toLocaleString('en-IN')} Duplicates Prevented)...`, 90);
                addModalLog(`Deduplication: ${duplicatesPrevented.toLocaleString('en-IN')} already-synced vouchers recognized and skipped, +${data.new_inserted || 0} new inserted.`, "SUCCESS");

                setTimeout(() => {
                    setModalPipelineStage(5, `Live Sync Complete · ${data.project_name} (${totalCount} Vouchers)`, 100);
                    addModalLog(`✓ Sync finished successfully for ${data.company}. Ready for GSTR-1 compilation.`, "SUCCESS");
                }, 200);

                appendLog('SUCCESS', `✓ Ingested ${totalCount} authentic vouchers from Tally (${data.company}), ${duplicatesPrevented.toLocaleString('en-IN')} duplicates prevented!`);

                // 1. Update Modal Headers & Details Cards
                const modalCompany = document.getElementById('modal-company-name');
                if (modalCompany) {
                    modalCompany.textContent = data.company || 'SUN BUILDERS';
                    modalCompany.title = data.company || '';
                }

                const modalProject = document.getElementById('modal-project-name');
                if (modalProject) {
                    modalProject.textContent = `Project: ${data.project_name || 'Sun Builders'} (${data.project_code || ''})`;
                }

                const modalVchs = document.getElementById('modal-total-vouchers');
                if (modalVchs) {
                    modalVchs.textContent = `${totalCount.toLocaleString('en-IN')} Vouchers`;
                }

                const modalDedup = document.getElementById('modal-dedup-status');
                if (modalDedup) {
                    modalDedup.textContent = `${duplicatesPrevented.toLocaleString('en-IN')} Duplicates Prevented`;
                }

                const modalDedupSub = document.getElementById('modal-dedup-sub');
                if (modalDedupSub) {
                    const unchanged = data.unchanged || totalCount;
                    const inserted = data.new_inserted || 0;
                    modalDedupSub.textContent = `${unchanged.toLocaleString('en-IN')} Verified · +${inserted} New`;
                }

                const modalGross = document.getElementById('modal-gross-cost');
                if (modalGross) {
                    const grossVal = Number(data.total_gross || 0);
                    modalGross.textContent = grossVal >= 10000000 ? `₹${(grossVal / 10000000).toFixed(2)} Cr` : `₹${grossVal.toLocaleString('en-IN')}`;
                }

                const modalTaxable = document.getElementById('modal-taxable-cost');
                if (modalTaxable) {
                    const taxVal = Number(data.total_taxable || 0);
                    modalTaxable.textContent = taxVal >= 10000000 ? `₹${(taxVal / 10000000).toFixed(2)} Cr` : `₹${taxVal.toLocaleString('en-IN')}`;
                }

                const connBadgeText = document.getElementById('modal-conn-text');
                if (connBadgeText) {
                    connBadgeText.textContent = 'Port 9000 Active';
                    if (connBadgeText.parentElement) {
                        connBadgeText.parentElement.className = 'px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200 inline-flex items-center gap-1';
                    }
                }

                // 2. Render Vouchers Table in Modal
                currentModalVouchers = data.vouchers || [];
                renderModalTable(currentModalVouchers);

                // 3. Update Main Overview Page
                const barCompany = document.getElementById('bar-active-company');
                if (barCompany && data.company) {
                    barCompany.textContent = data.company;
                }

                const projSelect = document.getElementById('select-voucher-project');
                if (projSelect && data.project_code) {
                    ensureProjectInSelect(projSelect, data.project_code, `🏢 ${data.project_name} (${data.project_code})`);
                    projSelect.value = data.project_code;
                }

                await loadRealVouchers(data.project_code);
                await checkStatus();
                loadActivityLogs();
            } else {
                setModalPipelineStage(1, `Tally Notice: ${data.message || 'Ready'}`, 50);
                addModalLog(`Notice: ${data.message}`, "WARN");
                appendLog('INFO', `[Sync Status]: ${data.message || 'Ready'}`);
                if (modalTbody) {
                    modalTbody.innerHTML = `<tr><td colspan="9" class="text-center py-8 text-amber-700 font-sans">
                        <div class="flex flex-col items-center justify-center gap-1.5">
                            <span class="material-symbols-outlined text-[28px] text-amber-500">warning</span>
                            <span class="font-bold">${data.message || 'Could not connect to Tally'}</span>
                        </div>
                    </td></tr>`;
                }
            }
        } catch (err) {
            setModalPipelineStage(1, `Error: ${err.message}`, 0);
            addModalLog(`Sync Error: ${err.message}`, "ERROR");
            appendLog('ERROR', `Live sync notice: ${err.message}`);
            if (modalTbody) {
                modalTbody.innerHTML = `<tr><td colspan="9" class="text-center py-8 text-red-600 font-sans">
                    <span class="font-bold">Sync error: ${err.message}</span>
                </td></tr>`;
            }
        } finally {
            if (triggerBtn) {
                triggerBtn.disabled = false;
                triggerBtn.innerHTML = originalContent;
            }
        }
    }

    // Modal Search Filter Handler
    const modalSearchInput = document.getElementById('modal-voucher-search');
    if (modalSearchInput) {
        modalSearchInput.addEventListener('input', (e) => {
            const query = e.target.value.toLowerCase().trim();
            if (!query) {
                renderModalTable(currentModalVouchers);
                return;
            }
            const filtered = currentModalVouchers.filter(v => {
                const num = String(v.vch_no || v.voucher_number || '').toLowerCase();
                const party = String(v.member_name || v.name || '').toLowerCase();
                const unit = String(v.flat_no || v.unit || '').toLowerCase();
                const proj = String(v.project || '').toLowerCase();
                return num.includes(query) || party.includes(query) || unit.includes(query) || proj.includes(query);
            });
            renderModalTable(filtered);
        });
    }

    const btnDumpAll = document.getElementById('btn-modal-dump-all');
    if (btnDumpAll) {
        btnDumpAll.addEventListener('click', () => {
            if (modalSearchInput) modalSearchInput.value = '';
            renderModalTable(currentModalVouchers);
            addModalLog(`Dumped all ${currentModalVouchers.length.toLocaleString('en-IN')} vouchers without filter (${currentModalDuplicatesPrevented.toLocaleString('en-IN')} duplicates prevented this sync).`, 'SUCCESS');
        });
    }

    // Wire up Modal Open / Close Buttons
    const syncModalElem = document.getElementById('sync-agent-modal');
    const closeSyncFunc = () => {
        if (syncModalElem) syncModalElem.classList.add('hidden');
    };

    const btnCloseModal = document.getElementById('btn-close-sync-modal');
    if (btnCloseModal) btnCloseModal.addEventListener('click', closeSyncFunc);

    const btnCloseFooter = document.getElementById('btn-close-sync-modal-footer');
    if (btnCloseFooter) btnCloseFooter.addEventListener('click', closeSyncFunc);

    if (syncModalElem) {
        syncModalElem.addEventListener('click', (e) => {
            if (e.target === syncModalElem) closeSyncFunc();
        });
    }

    const btnReextract = document.getElementById('btn-modal-reextract');
    if (btnReextract) {
        btnReextract.addEventListener('click', async () => {
            await executeTallyLiveSync(btnReextract);
        });
    }

    const btnModalViewMain = document.getElementById('btn-modal-view-main');
    if (btnModalViewMain) {
        btnModalViewMain.addEventListener('click', () => {
            closeSyncFunc();
            const hub = document.getElementById('voucher-hub-section');
            if (hub) hub.scrollIntoView({ behavior: 'smooth' });
        });
    }

    // 10. BU Permission Date & Statutory Cutoff Modal Handlers
    const buModal = document.getElementById('bu-modal');
    const btnOpenBuModal = document.getElementById('btn-open-bu-modal');
    const btnHeaderOpenBu = document.getElementById('btn-header-open-bu-modal');
    const btnProjectsTabOpenBu = document.getElementById('btn-projects-tab-open-bu');
    const btnCloseBuModal = document.getElementById('btn-close-bu-modal');
    const btnCloseBuCancel = document.getElementById('btn-close-bu-modal-cancel');
    const buSelectProject = document.getElementById('bu-select-project');
    const buRadioObtained = document.getElementById('bu-radio-obtained');
    const buRadioUnderCons = document.getElementById('bu-radio-under-construction');
    const buDetailsSection = document.getElementById('bu-details-section');
    const buInputDate = document.getElementById('bu-input-date');
    const buInputRate = document.getElementById('bu-input-rate');
    const buInputRef = document.getElementById('bu-input-ref');
    const buInputAuthority = document.getElementById('bu-input-authority');
    const buInputNotes = document.getElementById('bu-input-notes');
    const buImpactText = document.getElementById('bu-statutory-impact-text');
    const btnSaveBu = document.getElementById('btn-save-bu-settings');

    let cachedBuProjects = [
        { code: '010000', name: 'Sun Atmosphere', has_bu: true, bu_permission_date: '2024-03-07', bu_reference_no: 'BU/2024/AUDA/0712', authority: 'AUDA / AMC', rate: '1%', notes: 'BU Permission received on 07/03/2024. Advances received after 7th March 2024 are EXEMPT from GST.' },
        { code: '010010', name: 'Sun Footprint', has_bu: true, bu_permission_date: '2025-03-18', bu_reference_no: 'BU/2025/AMC/0189', authority: 'Ahmedabad Municipal Corporation (AMC)', rate: '1%', notes: 'BU Permission received on 18/03/2025. Advances received after 18th March 2025 are EXEMPT from GST.' },
        { code: '010011', name: 'Sun Park West', has_bu: false, bu_permission_date: '', bu_reference_no: '', authority: 'AUDA / AMC', rate: '5%', notes: 'Under Construction' },
        { code: '010009', name: 'Sun Gravitas Commercial', has_bu: true, bu_permission_date: '2022-06-18', bu_reference_no: 'BU/2022/AMC/0341', authority: 'AMC', rate: '18%', notes: 'Commercial offices with 1/3rd land abatement (Effective 12%).' },
        { code: '010002', name: 'Sun Silver Spring', has_bu: false, bu_permission_date: '', bu_reference_no: '', authority: 'AUDA', rate: '5%', notes: 'Premium residential.' },
        { code: '010015', name: 'Lekhambha', has_bu: false, bu_permission_date: '', bu_reference_no: '', authority: 'AUDA / Panchayat', rate: '5%', notes: 'Plotted development project.' }
    ];

    const closeBuModal = () => {
        if (buModal) {
            buModal.classList.add('hidden');
            buModal.style.display = 'none';
        }
    };

    const updateBuImpactText = () => {
        const hasBu = buRadioObtained && buRadioObtained.checked;
        const cutoffDate = buInputDate ? buInputDate.value : '';
        const rate = buInputRate ? buInputRate.value : '1%';
        
        if (hasBu && cutoffDate) {
            if (buImpactText) {
                buImpactText.innerHTML = `<strong>Legal Effect (CGST Act Sch III Entry 5):</strong> Building Use (BU) permission granted on <strong>${cutoffDate}</strong>. All collection vouchers received on or after <strong>${cutoffDate}</strong> are <strong>100% EXEMPT from GST</strong> (0% rate). Advances received prior to ${cutoffDate} remain taxable at <strong>${rate}</strong>.`;
            }
            if (buDetailsSection) buDetailsSection.classList.remove('opacity-50');
        } else {
            if (buImpactText) {
                buImpactText.innerHTML = `<strong>Legal Effect:</strong> Project is classified as <strong>Under Construction</strong>. No completion certificate cutoff applies. All eligible member collections will be classified as <strong>Taxable @ ${rate}</strong> with ₹0 post-BU exemption.`;
            }
            if (buDetailsSection) buDetailsSection.classList.add('opacity-50');
        }
    };

    const populateBuForm = (projectCode) => {
        if (!cachedBuProjects.length) return;
        const proj = cachedBuProjects.find(p => p.code === projectCode) || cachedBuProjects[0];
        if (!proj) return;

        if (buSelectProject) buSelectProject.value = proj.code;
        
        if (proj.has_bu) {
            if (buRadioObtained) buRadioObtained.checked = true;
        } else {
            if (buRadioUnderCons) buRadioUnderCons.checked = true;
        }

        if (buInputDate) buInputDate.value = proj.bu_permission_date || '2025-03-18';
        if (buInputRef) buInputRef.value = proj.bu_reference_no || '';
        if (buInputAuthority) buInputAuthority.value = proj.authority || 'Ahmedabad Municipal Corporation (AMC)';
        if (buInputNotes) buInputNotes.value = proj.notes || '';
        if (buInputRate) {
            buInputRate.value = proj.rate && proj.rate.includes('5%') ? '5%' : (proj.rate && proj.rate.includes('18%') ? '18%' : '1%');
        }

        updateBuImpactText();
    };

    const openBuModal = async (preselectCode) => {
        if (!buModal) return;
        
        // Show modal immediately
        buModal.classList.remove('hidden');
        buModal.style.display = 'flex';

        // Prepopulate with active or preselected code immediately from cache
        const activeCode = preselectCode || document.getElementById('select-voucher-project')?.value || document.getElementById('select-header-project')?.value || '010010';
        populateBuForm(activeCode);

        // Fetch latest from server in background
        try {
            const resp = await fetch('/api/projects/bu-settings');
            const data = await resp.json();
            if (data.status === 'success' && data.projects) {
                cachedBuProjects = data.projects;
                populateBuForm(activeCode);
            }
        } catch (e) {
            console.error('Error fetching BU settings:', e);
        }
    };

    // Expose globally so onclick="" handlers and external calls always work
    window.openBuModal = openBuModal;
    window.closeBuModal = closeBuModal;

    if (btnOpenBuModal) btnOpenBuModal.addEventListener('click', () => openBuModal());
    if (btnHeaderOpenBu) btnHeaderOpenBu.addEventListener('click', () => openBuModal());
    if (btnProjectsTabOpenBu) btnProjectsTabOpenBu.addEventListener('click', () => openBuModal());
    if (btnCloseBuModal) btnCloseBuModal.addEventListener('click', closeBuModal);
    if (btnCloseBuCancel) btnCloseBuCancel.addEventListener('click', closeBuModal);
    
    if (buModal) {
        buModal.addEventListener('click', (e) => {
            if (e.target === buModal) closeBuModal();
        });
    }

    if (buSelectProject) {
        buSelectProject.addEventListener('change', (e) => {
            populateBuForm(e.target.value);
        });
    }

    if (buRadioObtained) buRadioObtained.addEventListener('change', updateBuImpactText);
    if (buRadioUnderCons) buRadioUnderCons.addEventListener('change', updateBuImpactText);
    if (buInputDate) buInputDate.addEventListener('input', updateBuImpactText);
    if (buInputRate) buInputRate.addEventListener('change', updateBuImpactText);

    // Save BU Settings
    if (btnSaveBu) {
        btnSaveBu.addEventListener('click', async () => {
            const selectedCode = buSelectProject ? buSelectProject.value : '010010';
            const hasBu = buRadioObtained ? buRadioObtained.checked : false;
            const buDate = buInputDate ? buInputDate.value : null;
            const buRef = buInputRef ? buInputRef.value : '';
            const authority = buInputAuthority ? buInputAuthority.value : '';
            const notes = buInputNotes ? buInputNotes.value : '';
            const rate = buInputRate ? buInputRate.value : '1%';

            const origHtml = btnSaveBu.innerHTML;
            btnSaveBu.disabled = true;
            btnSaveBu.innerHTML = `<span class="material-symbols-outlined text-[18px] animate-spin">sync</span><span>Saving & Recalculating...</span>`;

            try {
                const resp = await fetch('/api/projects/bu-settings', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        code: selectedCode,
                        has_bu: hasBu,
                        bu_permission_date: buDate,
                        bu_reference_no: buRef,
                        authority: authority,
                        notes: notes,
                        rate: rate
                    })
                });

                const res = await resp.json();
                if (res.status === 'success') {
                    appendLog('SUCCESS', `🏛️ BU Permission updated for ${res.project.name} (${selectedCode}): ${hasBu ? 'Cutoff ' + buDate : 'Under Construction'}`);
                    appendLog('READY', `Recalculating member voucher ledger with updated legal cutoff...`);
                    
                    closeBuModal();

                    // Update table badge if present
                    const tableBadge = document.getElementById(`proj-bu-badge-${selectedCode}`);
                    if (tableBadge) {
                        if (hasBu && buDate) {
                            tableBadge.className = 'inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-secondary/10 text-secondary border border-secondary/30';
                            tableBadge.innerHTML = `<span class="material-symbols-outlined text-[10px]" style="font-variation-settings: 'FILL' 1;">check_circle</span> Obtained ${buDate}`;
                        } else {
                            tableBadge.className = 'inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-primary/10 text-primary border border-primary/30';
                            tableBadge.innerHTML = `<span class="material-symbols-outlined text-[10px]">pending</span> Under Construction`;
                        }
                    }

                    // If currently viewing vouchers, reload active project vouchers
                    const currentVoucherProject = document.getElementById('select-voucher-project')?.value || '010010';
                    await loadRealVouchers(currentVoucherProject);
                    await checkStatus();
                } else {
                    alert('Error saving BU settings: ' + (res.message || 'Unknown error'));
                }
            } catch (err) {
                alert('Network error saving BU settings: ' + err.message);
            } finally {
                btnSaveBu.disabled = false;
                btnSaveBu.innerHTML = origHtml;
            }
        });
    }

    // Quick-edit buttons in Projects Ledger table
    document.querySelectorAll('.btn-quick-edit-bu').forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.stopPropagation();
            const code = btn.getAttribute('data-code');
            openBuModal(code);
        });
    });

    // Units & Ownership tab wiring
    const unitsProjectSelect = document.getElementById('select-units-project');
    if (unitsProjectSelect) {
        unitsProjectSelect.addEventListener('change', (e) => loadUnits(e.target.value));
    }
    const unitsBlockSelect = document.getElementById('select-units-block');
    if (unitsBlockSelect) {
        unitsBlockSelect.addEventListener('change', (e) => {
            currentUnitsFilters.block = e.target.value;
            renderUnitsTable();
        });
    }
    document.querySelectorAll('.units-status-btn').forEach(btn => {
        if (btn.getAttribute('data-status') === 'ALL') {
            btn.className = 'units-status-btn px-3 py-1.5 rounded-lg text-xs font-bold transition-all bg-white text-blue-700 shadow-xs';
        } else {
            btn.className = 'units-status-btn px-3 py-1.5 rounded-lg text-xs font-bold transition-all text-slate-500 hover:text-slate-800';
        }
        btn.addEventListener('click', () => {
            currentUnitsFilters.status = btn.getAttribute('data-status');
            document.querySelectorAll('.units-status-btn').forEach(b => {
                b.className = b === btn
                    ? 'units-status-btn px-3 py-1.5 rounded-lg text-xs font-bold transition-all bg-white text-blue-700 shadow-xs'
                    : 'units-status-btn px-3 py-1.5 rounded-lg text-xs font-bold transition-all text-slate-500 hover:text-slate-800';
            });
            renderUnitsTable();
        });
    });
    const unitsSearchInput = document.getElementById('units-search-input');
    if (unitsSearchInput) {
        unitsSearchInput.addEventListener('input', (e) => {
            currentUnitsFilters.search = e.target.value;
            renderUnitsTable();
        });
    }
    const btnCloseUnitHistory = document.getElementById('btn-close-unit-history');
    if (btnCloseUnitHistory) {
        btnCloseUnitHistory.addEventListener('click', () => {
            document.getElementById('unit-history-modal')?.classList.add('hidden');
        });
    }
    const unitHistoryModal = document.getElementById('unit-history-modal');
    if (unitHistoryModal) {
        unitHistoryModal.addEventListener('click', (e) => {
            if (e.target === unitHistoryModal) unitHistoryModal.classList.add('hidden');
        });
    }
    const btnPrintStatement = document.getElementById('btn-print-unit-statement');
    if (btnPrintStatement) {
        btnPrintStatement.addEventListener('click', () => {
            window.print();
        });
    }

    // Escape key closes modals
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            document.getElementById('unit-history-modal')?.classList.add('hidden');
            closeOverrideModal();
        }
    });

    // Voucher classification override modal
    const btnCloseOverride = document.getElementById('btn-close-override-modal');
    if (btnCloseOverride) btnCloseOverride.addEventListener('click', closeOverrideModal);
    const btnCancelOverride = document.getElementById('btn-cancel-override');
    if (btnCancelOverride) btnCancelOverride.addEventListener('click', closeOverrideModal);
    const btnSaveOverride = document.getElementById('btn-save-override');
    if (btnSaveOverride) btnSaveOverride.addEventListener('click', () => saveVoucherOverride(false));
    const btnClearOverride = document.getElementById('btn-clear-override');
    if (btnClearOverride) {
        btnClearOverride.addEventListener('click', () => {
            if (confirm('Clear all manual overrides for this voucher and revert to auto-detected classification?')) {
                saveVoucherOverride(true);
            }
        });
    }
    const overrideModal = document.getElementById('voucher-override-modal');
    if (overrideModal) {
        overrideModal.addEventListener('click', (e) => {
            if (e.target === overrideModal) closeOverrideModal();
        });
    }

    // Add New Project Modal Wiring
    const btnOpenAddProject = document.getElementById('btn-open-add-project-modal');
    const modalAddProject = document.getElementById('modal-add-project');
    const btnCloseAddProject = document.getElementById('btn-close-add-project');
    const btnCancelAddProject = document.getElementById('btn-cancel-add-project');
    const btnSubmitAddProject = document.getElementById('btn-submit-add-project');
    const addBuRadioYes = document.getElementById('add-bu-radio-yes');
    const addBuRadioNo = document.getElementById('add-bu-radio-no');
    const addBuDetails = document.getElementById('add-bu-details');

    if (addBuRadioYes && addBuRadioNo && addBuDetails) {
        addBuRadioYes.addEventListener('change', () => {
            if (addBuRadioYes.checked) addBuDetails.classList.remove('hidden');
        });
        addBuRadioNo.addEventListener('change', () => {
            if (addBuRadioNo.checked) addBuDetails.classList.add('hidden');
        });
    }

    const openAddProjectModal = () => {
        if (modalAddProject) {
            modalAddProject.classList.remove('hidden');
            modalAddProject.style.display = 'flex';
        }
    };
    const closeAddProjectModal = () => {
        if (modalAddProject) {
            modalAddProject.classList.add('hidden');
            modalAddProject.style.display = 'none';
        }
    };

    if (btnOpenAddProject) btnOpenAddProject.addEventListener('click', openAddProjectModal);
    if (btnCloseAddProject) btnCloseAddProject.addEventListener('click', closeAddProjectModal);
    if (btnCancelAddProject) btnCancelAddProject.addEventListener('click', closeAddProjectModal);
    if (modalAddProject) {
        modalAddProject.addEventListener('click', (e) => {
            if (e.target === modalAddProject) closeAddProjectModal();
        });
    }

    if (btnSubmitAddProject) {
        btnSubmitAddProject.addEventListener('click', async () => {
            const name = document.getElementById('add-proj-name')?.value.trim();
            const code = document.getElementById('add-proj-code')?.value.trim();
            const aliases = document.getElementById('add-proj-aliases')?.value.trim();
            const type = document.getElementById('add-proj-type')?.value;
            const rate = document.getElementById('add-proj-rate')?.value;
            const hasBu = addBuRadioYes && addBuRadioYes.checked;
            const buDate = document.getElementById('add-bu-date')?.value;
            const authority = document.getElementById('add-bu-authority')?.value.trim();

            if (!name || !code) {
                alert('Please enter both Project Name and Project Code.');
                return;
            }

            btnSubmitAddProject.disabled = true;
            btnSubmitAddProject.innerHTML = '<span class="material-symbols-outlined text-[16px] animate-spin">sync</span> Creating...';

            try {
                const resp = await fetch('/api/projects/create', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        name: name,
                        code: code,
                        aliases: aliases,
                        type: type,
                        rate: rate,
                        has_bu: hasBu,
                        bu_permission_date: hasBu ? buDate : null,
                        authority: authority
                    })
                });
                const res = await resp.json();
                if (res.status === 'success') {
                    alert(`✅ Project '${name}' (${code}) added successfully!\n\nIt is now registered for automated Tally extraction, BU rules, and GSTR-1 calculation.`);
                    closeAddProjectModal();
                    
                    // Add to dropdowns
                    const headerSelect = document.getElementById('select-header-project');
                    if (headerSelect) {
                        const opt = document.createElement('option');
                        opt.value = code;
                        opt.textContent = `${name} (${code})`;
                        opt.className = 'bg-white text-slate-800';
                        headerSelect.appendChild(opt);
                        headerSelect.value = code;
                    }
                    const vchSelect = document.getElementById('select-voucher-project');
                    if (vchSelect) {
                        const opt = document.createElement('option');
                        opt.value = code;
                        opt.textContent = `${name} (${code})`;
                        vchSelect.appendChild(opt);
                        vchSelect.value = code;
                    }
                    const buProjSelect = document.getElementById('bu-select-project');
                    if (buProjSelect) {
                        const opt = document.createElement('option');
                        opt.value = code;
                        opt.textContent = `🏢 ${name} (${code})`;
                        buProjSelect.appendChild(opt);
                    }

                    // Append row to Projects Ledger table
                    const tbody = document.getElementById('project-table-body');
                    if (tbody) {
                        const tr = document.createElement('tr');
                        tr.className = 'hover:bg-blue-50/40 transition-colors group bg-blue-50/20';
                        tr.innerHTML = `
                            <td class="py-3 px-4 text-slate-900 sticky left-0 bg-white group-hover:bg-slate-50 transition-colors z-10 border-r border-slate-100">
                                <div class="font-display text-sm font-bold text-blue-700">${name}</div>
                                <div class="font-mono text-[11px] text-slate-500">${code} • Active Portfolio</div>
                            </td>
                            <td class="py-3 px-4">
                                <span class="px-2.5 py-0.5 rounded-md text-xs bg-slate-100 text-slate-700 border border-slate-200 font-medium">${type}</span>
                            </td>
                            <td class="py-3 px-4">
                                <span class="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold ${hasBu ? 'bg-emerald-50 text-emerald-700 border border-emerald-200' : 'bg-blue-50 text-blue-700 border border-blue-200'} shadow-xs">
                                    <span class="material-symbols-outlined text-[11px]">${hasBu ? 'check_circle' : 'pending'}</span>
                                    ${hasBu && buDate ? `Obtained ${buDate}` : 'Under Construction'}
                                </span>
                            </td>
                            <td class="py-3 px-3 text-right font-mono text-slate-800">0</td>
                            <td class="py-3 px-4 text-right font-mono text-slate-900 font-semibold">₹0</td>
                            <td class="py-3 px-4 text-right font-mono text-slate-500">₹0</td>
                            <td class="py-3 px-4 text-right font-mono text-emerald-700 font-bold bg-emerald-50/50">₹0</td>
                            <td class="py-3 px-4 text-right font-mono text-blue-700 font-bold bg-blue-50/50">₹0</td>
                            <td class="py-3 px-3 text-center font-mono font-bold text-blue-700">${rate}</td>
                            <td class="py-3 px-4 text-right font-mono text-slate-900 font-bold">₹0</td>
                        `;
                        tbody.appendChild(tr);
                    }
                } else {
                    alert('Error adding project: ' + (res.message || 'Unknown error'));
                }
            } catch (err) {
                alert('Network error adding project: ' + err.message);
            } finally {
                btnSubmitAddProject.disabled = false;
                btnSubmitAddProject.innerHTML = '<span class="material-symbols-outlined text-[16px]">add_circle</span><span>Create & Register Project</span>';
            }
        });
    }

    // =========================================================================
    // PROJECT PLAN & UNIT INVENTORY (GENERATOR & EXCEL UPLOAD) WIRING
    // =========================================================================
    const modalProjectPlan = document.getElementById('modal-project-plan');
    const btnOpenPlanModal = document.getElementById('btn-open-plan-modal');
    const btnProjectsTabOpenPlan = document.getElementById('btn-projects-tab-open-plan');
    const btnClosePlanModal = document.getElementById('btn-close-plan-modal');
    const btnCancelPlanModal = document.getElementById('btn-cancel-plan-modal');
    const btnCancelPlanModal2 = document.getElementById('btn-cancel-plan-modal-2');
    const planSelectProject = document.getElementById('plan-select-project');

    const btnPlanTabGen = document.getElementById('btn-plan-tab-gen');
    const btnPlanTabUp = document.getElementById('btn-plan-tab-up');
    const panePlanGen = document.getElementById('pane-plan-gen');
    const panePlanUpload = document.getElementById('pane-plan-upload');

    const populatePlanProjectDropdown = () => {
        if (!planSelectProject) return;
        const headerSelect = document.getElementById('select-header-project') || document.getElementById('select-units-project');
        if (headerSelect && headerSelect.options.length > 0) {
            planSelectProject.innerHTML = '';
            for (let opt of headerSelect.options) {
                const newOpt = document.createElement('option');
                newOpt.value = opt.value;
                newOpt.textContent = opt.textContent;
                planSelectProject.appendChild(newOpt);
            }
        }
        const activeUnitsProject = document.getElementById('select-units-project')?.value;
        if (activeUnitsProject && planSelectProject) {
            planSelectProject.value = activeUnitsProject;
        }
    };

    const openProjectPlanModal = () => {
        populatePlanProjectDropdown();
        if (modalProjectPlan) {
            modalProjectPlan.classList.remove('hidden');
            modalProjectPlan.style.display = 'flex';
        }
    };

    const closeProjectPlanModal = () => {
        if (modalProjectPlan) {
            modalProjectPlan.classList.add('hidden');
            modalProjectPlan.style.display = 'none';
        }
    };

    window.openProjectPlanModal = openProjectPlanModal;
    window.closeProjectPlanModal = closeProjectPlanModal;

    if (btnOpenPlanModal) btnOpenPlanModal.addEventListener('click', openProjectPlanModal);
    if (btnProjectsTabOpenPlan) btnProjectsTabOpenPlan.addEventListener('click', openProjectPlanModal);
    if (btnClosePlanModal) btnClosePlanModal.addEventListener('click', closeProjectPlanModal);
    if (btnCancelPlanModal) btnCancelPlanModal.addEventListener('click', closeProjectPlanModal);
    if (btnCancelPlanModal2) btnCancelPlanModal2.addEventListener('click', closeProjectPlanModal);

    // Tab switcher
    if (btnPlanTabGen && btnPlanTabUp && panePlanGen && panePlanUpload) {
        btnPlanTabGen.addEventListener('click', () => {
            btnPlanTabGen.className = 'flex-1 py-2 px-3 rounded-lg text-center transition-all bg-white text-indigo-700 shadow-xs';
            btnPlanTabUp.className = 'flex-1 py-2 px-3 rounded-lg text-center transition-all text-slate-600 hover:text-slate-900';
            panePlanGen.classList.remove('hidden');
            panePlanUpload.classList.add('hidden');
        });
        btnPlanTabUp.addEventListener('click', () => {
            btnPlanTabUp.className = 'flex-1 py-2 px-3 rounded-lg text-center transition-all bg-white text-indigo-700 shadow-xs';
            btnPlanTabGen.className = 'flex-1 py-2 px-3 rounded-lg text-center transition-all text-slate-600 hover:text-slate-900';
            panePlanUpload.classList.remove('hidden');
            panePlanGen.classList.add('hidden');
        });
    }

    // Live calculation for Rapid Generator
    const updatePlanSummary = () => {
        const blocksVal = (document.getElementById('plan-input-blocks')?.value || 'A').split(',').map(s => s.trim()).filter(Boolean);
        const startFl = parseInt(document.getElementById('plan-input-start-floor')?.value || '1', 10);
        const endFl = parseInt(document.getElementById('plan-input-end-floor')?.value || '14', 10);
        const flatsPerFl = parseInt(document.getElementById('plan-input-flats-per-floor')?.value || '4', 10);

        const numFloors = Math.max(0, (endFl - startFl) + 1);
        const totalFlats = blocksVal.length * numFloors * flatsPerFl;

        const summaryText = document.getElementById('plan-summary-text');
        if (summaryText) {
            summaryText.textContent = `${blocksVal.length} Tower${blocksVal.length > 1 ? 's' : ''} × ${numFloors} Floors × ${flatsPerFl} Flats = ${totalFlats} Total Flats`;
        }
    };

    ['plan-input-blocks', 'plan-input-start-floor', 'plan-input-end-floor', 'plan-input-flats-per-floor'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.addEventListener('input', updatePlanSummary);
    });

    // Submit Rapid Generator
    const btnSubmitGenPlan = document.getElementById('btn-submit-generate-plan');
    if (btnSubmitGenPlan) {
        btnSubmitGenPlan.addEventListener('click', async () => {
            const projCode = planSelectProject ? planSelectProject.value : '';
            if (!projCode) {
                alert('Please select a target project.');
                return;
            }

            const blocks = (document.getElementById('plan-input-blocks')?.value || 'A').split(',').map(s => s.trim()).filter(Boolean);
            const startFl = parseInt(document.getElementById('plan-input-start-floor')?.value || '1', 10);
            const endFl = parseInt(document.getElementById('plan-input-end-floor')?.value || '14', 10);
            const flatsPerFl = parseInt(document.getElementById('plan-input-flats-per-floor')?.value || '4', 10);
            const usage = document.getElementById('plan-input-usage')?.value || 'Residential';
            const size = parseFloat(document.getElementById('plan-input-size')?.value || '0');
            const carpet = parseFloat(document.getElementById('plan-input-carpet')?.value || '0');

            btnSubmitGenPlan.disabled = true;
            btnSubmitGenPlan.innerHTML = '<span class="material-symbols-outlined text-[16px] animate-spin">sync</span> Generating...';

            try {
                const resp = await fetch('/api/units/generate-plan', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        project_code: projCode,
                        blocks: blocks,
                        start_floor: startFl,
                        end_floor: endFl,
                        units_per_floor: flatsPerFl,
                        usage_type: usage,
                        size_sqft: size,
                        carpet_sqft: carpet
                    })
                });
                const res = await resp.json();
                if (res.status === 'success') {
                    alert(`✅ ${res.message}`);
                    closeProjectPlanModal();
                    
                    // Reload units tab if viewing this project
                    const unitsProj = document.getElementById('select-units-project');
                    if (unitsProj) {
                        unitsProj.value = projCode;
                        if (typeof loadUnits === 'function') loadUnits(projCode);
                    }
                } else {
                    alert('Error: ' + (res.message || 'Unknown error'));
                }
            } catch (err) {
                alert('Network error generating plan: ' + err.message);
            } finally {
                btnSubmitGenPlan.disabled = false;
                btnSubmitGenPlan.innerHTML = '<span class="material-symbols-outlined text-[16px]">domain_add</span><span>Generate & Register Inventory</span>';
            }
        });
    }

    // Submit Excel / CSV Upload
    const btnSubmitUploadPlan = document.getElementById('btn-submit-upload-plan');
    if (btnSubmitUploadPlan) {
        btnSubmitUploadPlan.addEventListener('click', async () => {
            const projCode = planSelectProject ? planSelectProject.value : '';
            if (!projCode) {
                alert('Please select a target project.');
                return;
            }

            const fileInput = document.getElementById('plan-file-input');
            if (!fileInput || !fileInput.files || fileInput.files.length === 0) {
                alert('Please select an Excel (.xlsx / .xls) or CSV file to upload.');
                return;
            }

            const file = fileInput.files[0];
            const formData = new FormData();
            formData.append('file', file);
            formData.append('project_code', projCode);

            btnSubmitUploadPlan.disabled = true;
            btnSubmitUploadPlan.innerHTML = '<span class="material-symbols-outlined text-[16px] animate-spin">sync</span> Uploading & Ingesting...';

            try {
                const resp = await fetch('/api/units/upload-excel', {
                    method: 'POST',
                    body: formData
                });
                const res = await resp.json();
                if (res.status === 'success') {
                    alert(`✅ ${res.message}`);
                    closeProjectPlanModal();
                    
                    const unitsProj = document.getElementById('select-units-project');
                    if (unitsProj) {
                        unitsProj.value = projCode;
                        if (typeof loadUnits === 'function') loadUnits(projCode);
                    }
                } else {
                    alert('Upload Error: ' + (res.message || 'Unknown error'));
                }
            } catch (err) {
                alert('Network error uploading file: ' + err.message);
            } finally {
                btnSubmitUploadPlan.disabled = false;
                btnSubmitUploadPlan.innerHTML = '<span class="material-symbols-outlined text-[16px]">upload_file</span><span>Upload & Ingest Unit Inventory</span>';
            }
        });
    }

    // Initialize Activity & Audit Trail Tracing Engine
    initActivityLoggingUI();
    loadActivityLogs();
});

// =========================================================================
// ACTIVITY LOGGING & AUDIT TRAIL TRACING ENGINE
// =========================================================================
let currentActivityLogs = [];
let activitySearchDebounceTimer = null;
let activityAutoRefreshTimer = null;

const ACTIVITY_TYPE_CONFIG = {
    'TALLY_SYNC': { label: 'Tally Sync', icon: 'sync_alt', bg: 'bg-blue-50 text-blue-700 border-blue-200' },
    'GSTR_GENERATE': { label: 'GSTR Gen', icon: 'assignment_turned_in', bg: 'bg-emerald-50 text-emerald-700 border-emerald-200' },
    'BU_DATE_UPDATE': { label: 'BU Date', icon: 'event', bg: 'bg-amber-50 text-amber-700 border-amber-200' },
    'VOUCHER_OVERRIDE': { label: 'Vch Override', icon: 'edit_note', bg: 'bg-purple-50 text-purple-700 border-purple-200' },
    'UNIT_BU_OVERRIDE': { label: 'Unit Override', icon: 'domain_verification', bg: 'bg-violet-50 text-violet-700 border-violet-200' },
    'UNIT_MASTER_IMPORT': { label: 'Unit Import', icon: 'upload_file', bg: 'bg-teal-50 text-teal-700 border-teal-200' },
    'UNIT_PLAN_GENERATE': { label: 'Plan Gen', icon: 'architecture', bg: 'bg-indigo-50 text-indigo-700 border-indigo-200' },
    'PURGE_VOUCHERS': { label: 'Dedup/Purge', icon: 'cleaning_services', bg: 'bg-rose-50 text-rose-700 border-rose-200' },
    'REPORT_DOWNLOAD': { label: 'Download', icon: 'download', bg: 'bg-sky-50 text-sky-700 border-sky-200' },
    'PROJECT_CONFIG': { label: 'Project Config', icon: 'settings', bg: 'bg-slate-100 text-slate-800 border-slate-300' },
    'SYSTEM_EVENT': { label: 'System Event', icon: 'dns', bg: 'bg-slate-100 text-slate-700 border-slate-200' }
};

function formatRelativeTime(dateStr) {
    if (!dateStr) return '—';
    try {
        const d = new Date(dateStr.replace(' ', 'T'));
        if (isNaN(d.getTime())) return dateStr;
        const now = new Date();
        const diffSec = Math.floor((now - d) / 1000);
        if (diffSec < 10) return 'Just now';
        if (diffSec < 60) return `${diffSec}s ago`;
        const diffMin = Math.floor(diffSec / 60);
        if (diffMin < 60) return `${diffMin}m ago`;
        const diffHr = Math.floor(diffMin / 60);
        if (diffHr < 24) return `${diffHr}h ago`;
        const diffDay = Math.floor(diffHr / 24);
        if (diffDay < 7) return `${diffDay}d ago`;
        return dateStr.split(' ')[0];
    } catch {
        return dateStr;
    }
}

async function loadActivityLogs() {
    const tableBody = document.getElementById('activity-table-body');
    const projectSel = document.getElementById('select-activity-project');
    const typeSel = document.getElementById('select-activity-type');
    const statusSel = document.getElementById('select-activity-status');
    const searchInput = document.getElementById('input-activity-search');
    const refreshIcon = document.getElementById('icon-refresh-activity');

    const project = projectSel ? projectSel.value : 'ALL';
    const type = typeSel ? typeSel.value : 'ALL';
    const status = statusSel ? statusSel.value : 'ALL';
    const search = searchInput ? searchInput.value.trim() : '';

    if (refreshIcon) refreshIcon.classList.add('animate-spin');

    try {
        const params = new URLSearchParams({
            project: project,
            type: type,
            status: status,
            search: search,
            limit: '100',
            offset: '0'
        });

        const resp = await fetch(`/api/activity-logs?${params.toString()}`);
        const data = await resp.json();

        if (data.status === 'success') {
            currentActivityLogs = data.logs || [];
            updateActivityStats(data.stats, data.total);
            renderActivityTable(currentActivityLogs);

            const countSum = document.getElementById('activity-count-summary');
            if (countSum) {
                countSum.textContent = `Showing ${currentActivityLogs.length} of ${data.total} logged activities`;
            }

            const badge = document.getElementById('nav-activity-count-badge');
            if (badge) {
                badge.textContent = data.total;
                badge.classList.remove('hidden');
            }
        }
    } catch (err) {
        console.error('Failed to load activity logs:', err);
        if (tableBody && (!currentActivityLogs || currentActivityLogs.length === 0)) {
            tableBody.innerHTML = `<tr><td colspan="6" class="py-8 text-center text-rose-500 font-mono text-xs">Failed to load activity logs: ${err.message}</td></tr>`;
        }
    } finally {
        if (refreshIcon) refreshIcon.classList.remove('animate-spin');
    }
}

function updateActivityStats(stats, total) {
    if (!stats) return;
    const statTotal = document.getElementById('stat-activity-total');
    const statSync = document.getElementById('stat-activity-sync');
    const statOverrides = document.getElementById('stat-activity-overrides');
    const statGstr = document.getElementById('stat-activity-gstr');
    const statLast = document.getElementById('stat-activity-last');

    if (statTotal) statTotal.textContent = total || stats.total || 0;

    const byType = stats.by_type || {};
    if (statSync) statSync.textContent = byType['TALLY_SYNC'] || 0;
    if (statOverrides) statOverrides.textContent = (byType['VOUCHER_OVERRIDE'] || 0) + (byType['UNIT_BU_OVERRIDE'] || 0);
    if (statGstr) statGstr.textContent = byType['GSTR_GENERATE'] || 0;

    if (statLast && stats.last_active) {
        statLast.textContent = formatRelativeTime(stats.last_active);
        statLast.title = stats.last_active;
    }
}

function renderActivityTable(logs) {
    const tableBody = document.getElementById('activity-table-body');
    if (!tableBody) return;

    if (!logs || logs.length === 0) {
        tableBody.innerHTML = `
            <tr>
                <td colspan="6" class="py-12 text-center text-slate-400">
                    <span class="material-symbols-outlined text-[36px] text-slate-300 block mx-auto mb-1.5">manage_search</span>
                    <span class="font-medium text-xs text-slate-600 block">No activity records match the current filters</span>
                    <span class="text-[11px] text-slate-400 block mt-0.5">Try clearing filters or performing actions like Tally Sync, BU edits, or GSTR generation</span>
                </td>
            </tr>
        `;
        return;
    }

    let html = '';
    logs.forEach(log => {
        const typeCfg = ACTIVITY_TYPE_CONFIG[log.activity_type] || {
            label: log.activity_type || 'ACTIVITY',
            icon: 'info',
            bg: 'bg-slate-100 text-slate-700 border-slate-200'
        };

        let statusClass = 'bg-emerald-50 text-emerald-700 border-emerald-200';
        let statusIcon = 'check_circle';
        if (log.status === 'ERROR') {
            statusClass = 'bg-rose-50 text-rose-700 border-rose-200';
            statusIcon = 'error';
        } else if (log.status === 'WARNING') {
            statusClass = 'bg-amber-50 text-amber-700 border-amber-200';
            statusIcon = 'warning';
        } else if (log.status === 'INFO') {
            statusClass = 'bg-blue-50 text-blue-700 border-blue-200';
            statusIcon = 'info';
        }

        const projectLabel = log.project_code ? (log.project_code === 'ALL' ? 'Consolidated' : (log.project_name || log.project_code)) : 'Global';
        const projectBadge = log.project_code ? `<span class="px-2 py-0.5 rounded text-[11px] font-mono font-medium bg-slate-100 text-slate-800 border border-slate-200/80" title="${log.project_code}">${escapeHtml(projectLabel)}</span>` : '<span class="text-slate-400">—</span>';

        const exactTime = log.created_at || '';
        const relTime = formatRelativeTime(exactTime);

        html += `
            <tr class="hover:bg-slate-50/80 transition-colors">
                <td class="py-3 px-4 font-mono text-xs whitespace-nowrap">
                    <div class="font-bold text-slate-800">${relTime}</div>
                    <div class="text-[10px] text-slate-400">${exactTime}</div>
                </td>
                <td class="py-3 px-3 whitespace-nowrap">
                    <span class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-semibold border ${typeCfg.bg}">
                        <span class="material-symbols-outlined text-[15px]">${typeCfg.icon}</span>
                        <span>${typeCfg.label}</span>
                    </span>
                </td>
                <td class="py-3 px-3 whitespace-nowrap">
                    ${projectBadge}
                </td>
                <td class="py-3 px-4">
                    <div class="font-semibold text-slate-900 text-xs">${escapeHtml(log.action || '')}</div>
                    <div class="text-xs text-slate-600 line-clamp-2 mt-0.5">${escapeHtml(log.description || '')}</div>
                </td>
                <td class="py-3 px-3 text-center whitespace-nowrap">
                    <span class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-bold font-mono border ${statusClass}">
                        <span class="material-symbols-outlined text-[13px]">${statusIcon}</span>
                        <span>${log.status || 'OK'}</span>
                    </span>
                </td>
                <td class="py-3 px-3 text-right whitespace-nowrap">
                    <button type="button" onclick="openActivityDetailModal(${log.id})" class="px-2.5 py-1 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-semibold border border-slate-200 shadow-2xs transition-colors inline-flex items-center gap-1 cursor-pointer">
                        <span class="material-symbols-outlined text-[14px]">visibility</span>
                        <span>View</span>
                    </button>
                </td>
            </tr>
        `;
    });

    tableBody.innerHTML = html;
}

function openActivityDetailModal(logId) {
    const log = currentActivityLogs.find(l => l.id === logId);
    if (!log) return;

    const modal = document.getElementById('modal-activity-detail');
    if (!modal) return;

    const titleElem = document.getElementById('modal-act-title');
    const subElem = document.getElementById('modal-act-subtitle');
    const descElem = document.getElementById('modal-act-description');
    const statusBadge = document.getElementById('modal-act-status-badge');
    const typeElem = document.getElementById('modal-act-type');
    const projElem = document.getElementById('modal-act-project');
    const timeElem = document.getElementById('modal-act-timestamp');
    const ipElem = document.getElementById('modal-act-ip');
    const jsonElem = document.getElementById('modal-act-json');

    if (titleElem) titleElem.textContent = log.action || 'Activity Log Entry';
    if (subElem) subElem.textContent = `Log ID #${log.id} • Registered ${log.created_at || ''}`;
    if (descElem) descElem.textContent = log.description || 'No detailed description provided.';

    if (statusBadge) {
        statusBadge.textContent = log.status || 'SUCCESS';
        if (log.status === 'ERROR') {
            statusBadge.className = 'px-2.5 py-0.5 rounded-full text-xs font-bold font-mono bg-rose-100 text-rose-800 border border-rose-200';
        } else if (log.status === 'WARNING') {
            statusBadge.className = 'px-2.5 py-0.5 rounded-full text-xs font-bold font-mono bg-amber-100 text-amber-800 border border-amber-200';
        } else {
            statusBadge.className = 'px-2.5 py-0.5 rounded-full text-xs font-bold font-mono bg-emerald-100 text-emerald-800 border border-emerald-200';
        }
    }

    if (typeElem) typeElem.textContent = log.activity_type || '—';
    if (projElem) projElem.textContent = log.project_code ? `${log.project_name || ''} (${log.project_code})` : 'Global System';
    if (timeElem) timeElem.textContent = `${log.created_at || '—'} (${formatRelativeTime(log.created_at)})`;
    if (ipElem) ipElem.textContent = log.ip_address || 'Internal Server';

    if (jsonElem) {
        const payload = log.details_parsed || log.details || { id: log.id, action: log.action, status: log.status };
        jsonElem.textContent = typeof payload === 'object' ? JSON.stringify(payload, null, 2) : payload;
    }

    modal.classList.remove('hidden');
}

function closeActivityDetailModal() {
    const modal = document.getElementById('modal-activity-detail');
    if (modal) modal.classList.add('hidden');
}

function escapeHtml(str) {
    if (!str) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

function initActivityLoggingUI() {
    const btnRefresh = document.getElementById('btn-refresh-activity-logs');
    if (btnRefresh) {
        btnRefresh.addEventListener('click', () => loadActivityLogs());
    }

    const btnExport = document.getElementById('btn-export-activity-logs');
    if (btnExport) {
        btnExport.addEventListener('click', () => {
            const project = document.getElementById('select-activity-project')?.value || 'ALL';
            const type = document.getElementById('select-activity-type')?.value || 'ALL';
            const status = document.getElementById('select-activity-status')?.value || 'ALL';
            const search = document.getElementById('input-activity-search')?.value.trim() || '';
            const params = new URLSearchParams({ project, type, status, search });
            window.location.href = `/api/activity-logs/export?${params.toString()}`;
        });
    }

    const searchInput = document.getElementById('input-activity-search');
    const clearSearchBtn = document.getElementById('btn-clear-activity-search');
    if (searchInput) {
        searchInput.addEventListener('input', () => {
            if (clearSearchBtn) {
                if (searchInput.value.trim()) clearSearchBtn.classList.remove('hidden');
                else clearSearchBtn.classList.add('hidden');
            }
            clearTimeout(activitySearchDebounceTimer);
            activitySearchDebounceTimer = setTimeout(() => {
                loadActivityLogs();
            }, 300);
        });
    }

    if (clearSearchBtn) {
        clearSearchBtn.addEventListener('click', () => {
            if (searchInput) searchInput.value = '';
            clearSearchBtn.classList.add('hidden');
            loadActivityLogs();
        });
    }

    ['select-activity-project', 'select-activity-type', 'select-activity-status'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.addEventListener('change', () => loadActivityLogs());
    });

    const btnClearFilters = document.getElementById('btn-clear-activity-filters');
    if (btnClearFilters) {
        btnClearFilters.addEventListener('click', () => {
            const p = document.getElementById('select-activity-project');
            const t = document.getElementById('select-activity-type');
            const s = document.getElementById('select-activity-status');
            const q = document.getElementById('input-activity-search');
            if (p) p.value = 'ALL';
            if (t) t.value = 'ALL';
            if (s) s.value = 'ALL';
            if (q) q.value = '';
            if (clearSearchBtn) clearSearchBtn.classList.add('hidden');
            loadActivityLogs();
        });
    }

    const btnCloseModal = document.getElementById('btn-close-activity-modal');
    const btnDoneModal = document.getElementById('btn-modal-done');
    const modal = document.getElementById('modal-activity-detail');
    if (btnCloseModal) btnCloseModal.addEventListener('click', closeActivityDetailModal);
    if (btnDoneModal) btnDoneModal.addEventListener('click', closeActivityDetailModal);
    if (modal) {
        modal.addEventListener('click', (e) => {
            if (e.target === modal) closeActivityDetailModal();
        });
    }

    const btnCopyJson = document.getElementById('btn-copy-activity-json');
    if (btnCopyJson) {
        btnCopyJson.addEventListener('click', () => {
            const jsonElem = document.getElementById('modal-act-json');
            if (jsonElem) {
                navigator.clipboard.writeText(jsonElem.textContent).then(() => {
                    btnCopyJson.innerHTML = '<span class="material-symbols-outlined text-[14px]">check</span><span>Copied!</span>';
                    setTimeout(() => {
                        btnCopyJson.innerHTML = '<span class="material-symbols-outlined text-[14px]">content_copy</span><span>Copy JSON</span>';
                    }, 2000);
                });
            }
        });
    }

    // Auto-refresh interval (every 10s if tab-audit is visible and checkbox checked)
    if (activityAutoRefreshTimer) clearInterval(activityAutoRefreshTimer);
    activityAutoRefreshTimer = setInterval(() => {
        const chk = document.getElementById('checkbox-activity-autorefresh');
        const auditTab = document.getElementById('tab-audit');
        if (chk && chk.checked && auditTab && !auditTab.classList.contains('hidden')) {
            loadActivityLogs();
        }
    }, 10000);
}


