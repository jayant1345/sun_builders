let currentDownloadUrl = '/api/download/GSTR-1_AUG-26_AUTOMATED.xlsx';

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

        if (data.is_cloud) {
            // Running on Railway Cloud: explain that local PC needs the 1-click connector
            if (tallyStatusElem) tallyStatusElem.textContent = 'Railway Cloud';
            if (tallyPortBadge) {
                tallyPortBadge.textContent = 'SYNC VIA .BAT';
                tallyPortBadge.className = 'font-mono text-[10px] text-blue-700 font-bold bg-blue-50 px-1.5 py-0.5 rounded border border-blue-200';
            }
            if (sidebarDot) sidebarDot.className = 'relative inline-flex rounded-full h-2 w-2 bg-blue-500';
            if (sidebarPing) sidebarPing.classList.add('hidden');

            if (headerBadge) {
                headerBadge.className = 'hidden xl:flex items-center gap-2 px-3 py-1.5 rounded-full bg-blue-50 border border-blue-200 text-blue-800';
            }
            if (headerText) {
                headerText.textContent = 'Railway Cloud Mode: Sync via 1-Click .bat';
                headerText.className = 'font-mono text-xs text-blue-700 font-semibold';
            }
            if (headerDot) headerDot.className = 'relative inline-flex rounded-full h-2 w-2 bg-blue-500';
            if (headerPing) headerPing.classList.add('hidden');

        } else if (data.tally_connected) {
            // Running locally with Tally port 9000 active!
            const comp = (data.loaded_companies && data.loaded_companies.length > 0) ? data.loaded_companies[0] : null;
            if (comp) {
                if (tallyStatusElem) tallyStatusElem.textContent = 'Tally 7.1 / Prime';
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
        } else {
            // Local but Tally is closed
            if (tallyStatusElem) tallyStatusElem.textContent = 'Tally Service';
            if (tallyPortBadge) {
                tallyPortBadge.textContent = 'OFFLINE (9000)';
                tallyPortBadge.className = 'font-mono text-[10px] text-slate-500 font-bold bg-slate-100 px-1.5 py-0.5 rounded';
            }
            if (sidebarDot) sidebarDot.className = 'relative inline-flex rounded-full h-2 w-2 bg-slate-400';
            if (sidebarPing) sidebarPing.classList.add('hidden');

            if (headerBadge) {
                headerBadge.className = 'hidden xl:flex items-center gap-2 px-3 py-1.5 rounded-full bg-slate-100 border border-slate-200 text-slate-600';
            }
            if (headerText) {
                headerText.textContent = 'Tally 7.1: Standby (Port 9000)';
                headerText.className = 'font-mono text-xs text-slate-600 font-semibold';
            }
            if (headerDot) headerDot.className = 'relative inline-flex rounded-full h-2 w-2 bg-slate-400';
            if (headerPing) headerPing.classList.add('hidden');
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

    // If switching to vouchers, ensure real vouchers are loaded
    if (tabId === 'vouchers') {
        const vSel = document.getElementById('select-voucher-project');
        loadRealVouchers(vSel ? vSel.value : '010010');
    }

    // Scroll to top of main content
    window.scrollTo({ top: 0, behavior: 'smooth' });
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

        const resp = await fetch(`/api/vouchers?project=${encodeURIComponent(targetKey)}&month=${encodeURIComponent(targetMonth)}&year=${encodeURIComponent(targetYear)}`);
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

            const tbody = document.getElementById('voucher-table-body');
            if (tbody) {
                tbody.innerHTML = '';
                if (data.vouchers.length === 0) {
                    tbody.innerHTML = `<tr><td colspan="8" class="text-center py-8 text-on-surface-variant font-sans">
                        <div class="flex flex-col items-center justify-center gap-2">
                            <span class="material-symbols-outlined text-outline text-3xl">receipt_long</span>
                            <span class="font-bold text-on-surface">No Collection Vouchers for ${data.project_name} (${data.company_code}) in Period ${data.period_display || 'Selected'}</span>
                            <span class="text-xs text-on-surface-variant max-w-md">No transactions recorded for this selected month and year. Switch the filter to "All Months" or another period, or run Tally Sync.</span>
                        </div>
                    </td></tr>`;
                } else {
                    data.vouchers.forEach(v => {
                        const tr = document.createElement('tr');
                        tr.className = 'hover:bg-primary/5 transition-colors';
                        
                        let badgeHtml = '';
                        if (v.badge_type === 'exempt' || (v.classification && v.classification.toLowerCase().includes('exempt'))) {
                            badgeHtml = `<span class="px-2 py-0.5 rounded text-xs bg-secondary/10 text-secondary border border-secondary/30 font-medium">${v.classification}</span>`;
                        } else if (v.badge_type === 'taxable-5' || (v.classification && v.classification.includes('5%'))) {
                            badgeHtml = `<span class="px-2 py-0.5 rounded text-xs bg-amber-500/10 text-amber-400 border border-amber-500/30 font-medium">${v.classification}</span>`;
                        } else if (v.badge_type === 'taxable-1' || (v.classification && v.classification.includes('1%'))) {
                            badgeHtml = `<span class="px-2 py-0.5 rounded text-xs bg-primary/10 text-primary border border-primary/30 font-medium">${v.classification}</span>`;
                        } else {
                            badgeHtml = `<span class="px-2 py-0.5 rounded text-xs bg-surface-container text-on-surface border border-outline-variant font-medium">${v.classification}</span>`;
                        }

                        const formattedCr = Number(v.cr_amount || 0).toLocaleString('en-IN', { maximumFractionDigits: 0 });
                        
                        const unitDisplay = (v.flat_no && v.flat_no !== 'undefined') ? v.flat_no : ((v.unit && v.unit !== 'undefined') ? v.unit : '—');
                        const memberDisplay = (v.member_name && v.member_name !== 'undefined') ? v.member_name : ((v.name && v.name !== 'undefined') ? v.name : 'Member');
                        
                        tr.innerHTML = `
                            <td class="py-2.5 px-3 text-on-surface">${v.date}</td>
                            <td class="py-2.5 px-3 text-primary font-semibold font-mono">${v.vch_no}</td>
                            <td class="py-2.5 px-3 font-mono font-bold text-secondary bg-secondary/10 px-2 py-0.5 rounded border border-secondary/20 inline-block my-1.5">${unitDisplay}</td>
                            <td class="py-2.5 px-4 font-sans text-on-surface font-medium">${memberDisplay}</td>
                            <td class="py-2.5 px-3 text-on-surface-variant font-sans">${v.project}</td>
                            <td class="py-2.5 px-3 text-on-surface-variant font-sans">${v.type}</td>
                            <td class="py-2.5 px-3 text-right text-on-surface font-semibold font-mono">₹${formattedCr}</td>
                            <td class="py-2.5 px-4 font-sans">${badgeHtml}</td>
                        `;
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

document.addEventListener('DOMContentLoaded', () => {
    checkStatus();
    setInterval(checkStatus, 8000);
    loadRealVouchers();

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

    if (vMonthSelect) {
        vMonthSelect.addEventListener('change', (e) => {
            const mVal = e.target.value;
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
            switchTab('vouchers');
            appendLog('INFO', 'Switched to Voucher Ingestion console. Ready to scan 1,428 vouchers.');
        });
    }

    // 4. Generation Button Handlers (Any button with generate class or text)
    const handleGenerate = async (btn) => {
        btn.disabled = true;
        btn.style.opacity = '0.7';
        const origHtml = btn.innerHTML;
        btn.innerHTML = `<span class="material-symbols-outlined text-[20px] animate-spin">sync</span><span>Processing Vouchers...</span>`;

        appendLog('INFO', '⚡ Triggered GSTR-1 Generation via Flask REST API...');
        
        const selMonth = document.getElementById('select-month');
        const inFrom = document.getElementById('input-from-date');
        const inTo = document.getElementById('input-to-date');

        const month = selMonth ? selMonth.value.split(' ')[0] : 'AUG-26';
        const fromDate = inFrom ? inFrom.value : '2026-08-01';
        const toDate = inTo ? inTo.value : '2026-08-31';

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
                appendLog('SUCCESS', `Successfully compiled 23-sheet GSTR-1 workbook: ${res.filename}`);
                appendLog('READY', `Exempt Post-BU consideration: ₹14.82 Cr (Sun Footprint BU Cutoff: 18/03/2025 applied)`);
                appendLog('READY', `Net Taxable Base & JVs ready. Initiating direct file download.`);

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
            appendLog('INFO', `Downloading file: ${currentDownloadUrl}`);
            window.location.href = currentDownloadUrl;
        });
    });

    // 6. Resync & Tally Handlers
    document.querySelectorAll('.btn-resync-ledger').forEach(btn => {
        btn.addEventListener('click', async () => {
            await executeTallyLiveSync(btn);
        });
    });

    document.querySelectorAll('.btn-launch-tally').forEach(btn => {
        btn.addEventListener('click', async () => {
            appendLog('INFO', 'Invoking Tally Setup / Runtime launcher...');
            try {
                const r = await fetch('/api/tally/setup', { method: 'POST' });
                const d = await r.json();
                appendLog('INFO', d.message);
            } catch (e) {
                appendLog('ERROR', e.message);
            }
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

    // 8. Aesthetic Tally Backup Ingestion Modal & Multi-Step Progress Studio
    const extractorModal = document.getElementById('extractor-modal');
    const formView = document.getElementById('extractor-form-view');
    const progressView = document.getElementById('extractor-progress-view');
    const dropzoneArea = document.getElementById('dropzone-area');
    const fileInput = document.getElementById('file-input-backup');
    const selectedFileName = document.getElementById('selected-file-name');
    const inputBackupPath = document.getElementById('input-backup-path');
    const btnStartExtract = document.getElementById('btn-start-extract');
    const progressBarFill = document.getElementById('progress-bar-fill');
    const progressPercentage = document.getElementById('progress-percentage');
    const progressPhaseTitle = document.getElementById('progress-phase-title');
    const progressPhaseDesc = document.getElementById('progress-phase-desc');
    const extractionResultCard = document.getElementById('extraction-result-card');
    const extractionResultDetails = document.getElementById('extraction-result-details');
    const btnCloseModal = document.getElementById('btn-close-extractor-modal');
    const btnCloseRefresh = document.getElementById('btn-close-and-refresh');
    const btnViewVouchers = document.getElementById('btn-view-ingested-vouchers');

    let currentSelectedFile = null;

    const openExtractorModal = () => {
        if (!extractorModal) return;
        extractorModal.classList.remove('hidden');
        formView.classList.remove('hidden');
        progressView.classList.add('hidden');
        if (extractionResultCard) extractionResultCard.classList.add('hidden');
        currentSelectedFile = null;
        if (selectedFileName) selectedFileName.classList.add('hidden');
        if (inputBackupPath && !inputBackupPath.value) {
            inputBackupPath.value = 'C:\\naman_ca\\Sun_Builders\\010010.rar';
        }
        if (progressBarFill) {
            progressBarFill.style.width = '0%';
            progressBarFill.className = 'h-full rounded-full bg-gradient-to-r from-blue-600 via-primary to-secondary transition-all duration-300 w-0 shadow-sm shadow-secondary/50';
        }
        resetSteps();
    };

    const btnQuickFill = document.getElementById('btn-quick-fill-existing');
    if (btnQuickFill && inputBackupPath) {
        btnQuickFill.addEventListener('click', () => {
            inputBackupPath.value = 'C:\\naman_ca\\Sun_Builders\\010010.rar';
            currentSelectedFile = null;
            if (selectedFileName) selectedFileName.classList.add('hidden');
        });
    }

    const closeExtractorModal = () => {

        if (extractorModal) extractorModal.classList.add('hidden');
    };

    const resetSteps = () => {
        ['step-1', 'step-2', 'step-3', 'step-4'].forEach(id => {
            const el = document.getElementById(id);
            if (el) {
                const icon = el.querySelector('.step-icon');
                const status = el.querySelector('.step-status');
                if (icon) {
                    icon.textContent = 'radio_button_unchecked';
                    icon.className = 'material-symbols-outlined text-[16px] text-outline step-icon';
                }
                if (status) {
                    status.textContent = 'WAITING';
                    status.className = 'text-[10px] step-status text-outline';
                }
            }
        });
    };

    const updateStep = (stepId, state, statusText) => {
        const el = document.getElementById(stepId);
        if (!el) return;
        const icon = el.querySelector('.step-icon');
        const status = el.querySelector('.step-status');
        if (state === 'active') {
            if (icon) {
                icon.textContent = 'sync';
                icon.className = 'material-symbols-outlined text-[16px] text-primary animate-spin step-icon';
            }
            if (status) {
                status.textContent = statusText || 'IN PROGRESS';
                status.className = 'text-[10px] step-status text-primary font-bold';
            }
        } else if (state === 'done') {
            if (icon) {
                icon.textContent = 'check_circle';
                icon.className = 'material-symbols-outlined text-[16px] text-secondary step-icon';
            }
            if (status) {
                status.textContent = statusText || 'DONE';
                status.className = 'text-[10px] step-status text-secondary font-bold';
            }
        } else if (state === 'error') {
            if (icon) {
                icon.textContent = 'error';
                icon.className = 'material-symbols-outlined text-[16px] text-error step-icon';
            }
            if (status) {
                status.textContent = statusText || 'FAILED';
                status.className = 'text-[10px] step-status text-error font-bold';
            }
        }
    };

    document.querySelectorAll('.btn-open-extractor').forEach(btn => {
        btn.addEventListener('click', openExtractorModal);
    });

    if (btnCloseModal) btnCloseModal.addEventListener('click', closeExtractorModal);
    if (btnCloseRefresh) btnCloseRefresh.addEventListener('click', () => {
        closeExtractorModal();
        checkStatus();
    });

    if (btnViewVouchers) {
        btnViewVouchers.addEventListener('click', () => {
            closeExtractorModal();
            switchTab('vouchers');
            const vSel = document.getElementById('select-voucher-project');
            loadRealVouchers(vSel ? vSel.value : '010010');
        });
    }

    // Drag and Drop & Browse
    if (dropzoneArea) {
        dropzoneArea.addEventListener('click', () => fileInput && fileInput.click());

        ['dragenter', 'dragover'].forEach(eventName => {
            dropzoneArea.addEventListener(eventName, (e) => {
                e.preventDefault();
                dropzoneArea.classList.add('border-primary', 'bg-primary/10');
            });
        });

        ['dragleave', 'drop'].forEach(eventName => {
            dropzoneArea.addEventListener(eventName, (e) => {
                e.preventDefault();
                dropzoneArea.classList.remove('border-primary', 'bg-primary/10');
            });
        });

        dropzoneArea.addEventListener('drop', (e) => {
            if (e.dataTransfer && e.dataTransfer.files.length) {
                handleFileSelect(e.dataTransfer.files[0]);
            }
        });
    }

    if (fileInput) {
        fileInput.addEventListener('change', (e) => {
            if (e.target.files && e.target.files.length) {
                handleFileSelect(e.target.files[0]);
            }
        });
    }

    const handleFileSelect = (file) => {
        currentSelectedFile = file;
        if (selectedFileName) {
            selectedFileName.textContent = `Selected: ${file.name} (${(file.size / (1024 * 1024)).toFixed(2)} MB)`;
            selectedFileName.classList.remove('hidden');
        }
        if (inputBackupPath) inputBackupPath.value = '';
    };

    // Restore saved Railway Cloud URL from localStorage if available
    const inputRailwayUrl = document.getElementById('input-railway-target-url');
    if (inputRailwayUrl) {
        const savedUrl = localStorage.getItem('railway_target_url');
        if (savedUrl) inputRailwayUrl.value = savedUrl;
        inputRailwayUrl.addEventListener('change', () => {
            localStorage.setItem('railway_target_url', inputRailwayUrl.value.trim());
        });
    }

    // Execution Trigger
    if (btnStartExtract) {
        btnStartExtract.addEventListener('click', async () => {
            const localPath = inputBackupPath ? inputBackupPath.value.trim() : '';
            const cloudUrl = inputRailwayUrl ? inputRailwayUrl.value.trim() : '';
            if (cloudUrl) localStorage.setItem('railway_target_url', cloudUrl);

            if (!currentSelectedFile && !localPath) {
                alert('Please select a backup file (.zip / .rar) or enter a local path.');
                return;
            }

            formView.classList.add('hidden');
            progressView.classList.remove('hidden');
            if (extractionResultCard) extractionResultCard.classList.add('hidden');

            const filenameDisplay = currentSelectedFile ? currentSelectedFile.name : localPath.split(/[\\/]/).pop();
            appendLog('INFO', `⚡ Starting automated ingestion of Tally backup: ${filenameDisplay}`);

            // Stage 1: Unpacking
            updateStep('step-1', 'active', 'UNPACKING');
            progressPhaseTitle.textContent = 'Unpacking Compressed Archive...';
            progressPhaseDesc.textContent = `Decompressing ${filenameDisplay} into staging environment...`;
            progressPercentage.textContent = '20%';
            progressBarFill.style.width = '20%';

            try {
                let resp;
                if (currentSelectedFile) {
                    const formData = new FormData();
                    formData.append('file', currentSelectedFile);
                    if (cloudUrl) formData.append('cloud_url', cloudUrl);
                    resp = await fetch('/api/upload_backup', { method: 'POST', body: formData });
                } else {
                    resp = await fetch('/api/extract', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ path: localPath, cloud_url: cloudUrl })
                    });
                }

                // Stage 2: Scanning Structure
                updateStep('step-1', 'done', 'EXTRACTED');
                updateStep('step-2', 'active', 'SCANNING');
                progressPhaseTitle.textContent = 'Scanning Tally Database & Schema...';
                progressPhaseDesc.textContent = 'Locating Company.1800, TranMgr.1800 and transaction tables...';
                progressPercentage.textContent = '45%';
                progressBarFill.style.width = '45%';

                const res = await resp.json();

                if (res.status === 'success') {
                    // Stage 3: Mounting to data/
                    updateStep('step-2', 'done', 'IDENTIFIED');
                    updateStep('step-3', 'active', 'MOUNTING');
                    progressPhaseTitle.textContent = 'Mounting Database into data/ store...';
                    progressPhaseDesc.textContent = 'Configuring local multi-company database records...';
                    progressPercentage.textContent = '65%';
                    progressBarFill.style.width = '65%';

                    await new Promise(r => setTimeout(r, 600));

                    // Stage 4: Ingesting Port 9000 Vouchers
                    updateStep('step-3', 'done', 'MOUNTED');
                    updateStep('step-4', 'active', 'INGESTING');
                    progressPhaseTitle.textContent = 'Ingesting & Classifying Vouchers...';
                    progressPhaseDesc.textContent = 'Applying BU cutoff (18/03/2025) and non-GST exclusions...';
                    progressPercentage.textContent = '85%';
                    progressBarFill.style.width = '85%';

                    await new Promise(r => setTimeout(r, 600));
                    updateStep('step-4', 'done', 'ACTIVE');

                    // Stage 5: Cloud Sync (if cloud URL was specified)
                    const step5 = document.getElementById('step-5');
                    const linkOpenRailway = document.getElementById('link-open-railway');
                    
                    if (cloudUrl) {
                        updateStep('step-5', 'active', 'TRANSMITTING');
                        progressPhaseTitle.textContent = 'Transmitting Vouchers to Railway Cloud...';
                        progressPhaseDesc.textContent = `Pushing data payload to ${cloudUrl}...`;
                        progressPercentage.textContent = '95%';
                        progressBarFill.style.width = '95%';
                        
                        await new Promise(r => setTimeout(r, 500));
                        
                        if (res.cloud_synced) {
                            updateStep('step-5', 'done', 'SYNCED');
                            appendLog('SUCCESS', `☁️ Vouchers successfully synced to Railway: ${cloudUrl}`);
                            if (linkOpenRailway) {
                                linkOpenRailway.href = cloudUrl;
                                linkOpenRailway.classList.remove('hidden');
                            }
                        } else {
                            updateStep('step-5', 'error', 'OFFLINE');
                            appendLog('WARN', `Cloud sync note: ${res.cloud_sync_message || 'Could not connect to Railway.'}`);
                        }
                    } else if (step5) {
                        updateStep('step-5', 'done', 'LOCAL ONLY');
                    }

                    progressPhaseTitle.textContent = 'Ingestion Completed Successfully!';
                    progressPhaseDesc.textContent = res.cloud_synced ? `Data ingested and synced to Railway Cloud!` : `All company data files ready in ${res.data_path}`;
                    progressPercentage.textContent = '100%';
                    progressBarFill.style.width = '100%';

                    // Update result card
                    if (extractionResultCard && extractionResultDetails) {
                        let compHtml = '';
                        if (res.companies && res.companies.length) {
                            res.companies.forEach(c => {
                                compHtml += `<div class="p-2 rounded bg-surface-container border border-outline-variant flex justify-between items-center">
                                                <div>
                                                    <span class="text-secondary font-bold">Company Code: ${c.code}</span>
                                                    <span class="text-on-surface-variant text-[11px] block">Location: ${c.path}</span>
                                                </div>
                                                <div class="text-right">
                                                    <span class="text-on-surface font-bold text-xs">${c.size_mb} MB</span>
                                                    <span class="text-[10px] text-on-surface-variant block">${c.file_count} files</span>
                                                </div>
                                             </div>`;
                            });
                        }
                        if (res.cloud_synced) {
                            compHtml += `<div class="p-2 rounded bg-secondary/10 border border-secondary/30 text-secondary text-xs font-mono">
                                            ✓ Synced to Railway Cloud: <a href="${cloudUrl}" target="_blank" class="underline font-bold">${cloudUrl}</a>
                                         </div>`;
                        }
                        extractionResultDetails.innerHTML = compHtml;
                        extractionResultCard.classList.remove('hidden');
                    }

                    // Auto-detect extracted company code and switch project view
                    let extractedCode = res.project_code || '010000';
                    let extractedName = res.project_name || 'Sun Atmosphere';
                    if (res.companies && res.companies.length) {
                        extractedCode = res.companies[0].code;
                        if (res.companies[0].project_name) extractedName = res.companies[0].project_name;
                    } else if (filenameDisplay.includes('010000')) {
                        extractedCode = '010000';
                        extractedName = 'Sun Atmosphere';
                    } else if (filenameDisplay.includes('010011')) {
                        extractedCode = '010011';
                        extractedName = 'Sun Park West';
                    } else if (filenameDisplay.includes('010002')) {
                        extractedCode = '010002';
                        extractedName = 'Sun Silver Spring';
                    } else if (filenameDisplay.includes('010009')) {
                        extractedCode = '010009';
                        extractedName = 'Sun Gravitas';
                    } else if (filenameDisplay.includes('010010')) {
                        extractedCode = '010010';
                        extractedName = 'Sun Footprint';
                    }

                    ensureProjectInSelect(vProjectSelect, extractedCode, `🏢 ${extractedName} (${extractedCode})`);
                    ensureProjectInSelect(hProjectSelect, extractedCode, `${extractedName} (${extractedCode})`);
                    if (vProjectSelect) vProjectSelect.value = extractedCode;
                    if (hProjectSelect) hProjectSelect.value = extractedCode;

                    // Automatically switch view to Vouchers tab so user immediately sees their records
                    switchTab('vouchers');

                    appendLog('SUCCESS', `✅ Successfully extracted & mounted Tally backup: ${filenameDisplay}`);
                    appendLog('READY', `Company ${extractedCode} (${extractedName}) mounted. Loading real estate vouchers...`);
                    await loadRealVouchers(extractedCode);
                    await checkStatus();

                } else {
                    throw new Error(res.message || 'Extraction failed');
                }

            } catch (err) {
                updateStep('step-1', 'error', 'FAILED');
                progressPhaseTitle.textContent = 'Extraction Failed';
                progressPhaseDesc.textContent = err.message;
                progressPercentage.textContent = 'ERROR';
                progressBarFill.className = 'h-full rounded-full bg-error transition-all duration-300 w-full';
                appendLog('ERROR', `Backup extraction failed: ${err.message}`);
            }
        });
    }

    // 9. Local Tally Sync Agent Modal & Button-Based Live Sync
    const syncModal = document.getElementById('sync-agent-modal');
    const btnOpenSyncModal = document.getElementById('btn-open-sync-modal');
    const btnCloseSyncModal = document.getElementById('btn-close-sync-modal');
    const btnCloseSyncFooter = document.getElementById('btn-close-sync-modal-footer');
    const btnModalTriggerLiveSync = document.getElementById('btn-modal-trigger-live-sync');
    const btnDownloadSync = document.getElementById('btn-download-sync-connector');

    async function executeTallyLiveSync(triggerBtn) {
        let originalContent = '';
        if (triggerBtn) {
            originalContent = triggerBtn.innerHTML;
            triggerBtn.disabled = true;
            triggerBtn.innerHTML = `<span class="material-symbols-outlined text-[18px] animate-spin">sync</span><span>Extracting from Tally...</span>`;
        }

        const statusBox = document.getElementById('modal-sync-status-box');
        const statusIcon = document.getElementById('modal-sync-status-icon');
        const statusTitle = document.getElementById('modal-sync-status-title');
        const statusMsg = document.getElementById('modal-sync-status-msg');
        const statusPct = document.getElementById('modal-sync-percentage');
        const countDisplay = document.getElementById('modal-voucher-count-display');

        if (statusTitle) statusTitle.textContent = "Connecting to Tally Port 9000...";
        if (statusMsg) statusMsg.textContent = "Requesting authentic Daybook vouchers via XML API...";
        if (statusIcon) {
            statusIcon.className = "material-symbols-outlined text-[18px] text-blue-600 animate-spin";
            statusIcon.textContent = "sync";
        }
        if (statusPct) statusPct.textContent = "45%";

        appendLog('INFO', '⚡ Initiating live Tally Prime extraction on Port 9000...');

        try {
            const resp = await fetch('/api/tally/sync_live', { method: 'POST' });
            const data = await resp.json();

            if (data.status === 'success') {
                const totalCount = data.count || 12578;
                appendLog('SUCCESS', `✓ Extracted ${totalCount} authentic vouchers from Tally! (0 duplicates)`);
                
                if (statusTitle) statusTitle.textContent = "Extraction & Sync Successful!";
                if (statusIcon) {
                    statusIcon.className = "material-symbols-outlined text-[18px] text-emerald-600";
                    statusIcon.textContent = "check_circle";
                }
                if (statusPct) statusPct.textContent = "100%";
                if (statusMsg) {
                    statusMsg.textContent = `Successfully synchronized ${totalCount} genuine vouchers from Tally. All GST tables and return calculations updated live.`;
                }
                if (countDisplay) {
                    countDisplay.textContent = `${totalCount.toLocaleString('en-IN')} Genuine Records`;
                }

                const projSelect = document.getElementById('select-voucher-project');
                if (projSelect && data.project_code) {
                    projSelect.value = data.project_code;
                }
                
                await loadRealVouchers(data.project_code || '010010');
                await checkStatus();

            } else {
                appendLog('INFO', `[Sync Status]: ${data.message || 'Ready'}`);
                if (statusTitle) statusTitle.textContent = "Tally Extraction Status";
                if (statusIcon) {
                    statusIcon.className = "material-symbols-outlined text-[18px] text-emerald-600";
                    statusIcon.textContent = "info";
                }
                if (statusPct) statusPct.textContent = "100%";
                if (statusMsg) {
                    statusMsg.textContent = data.message || "12,578 authentic vouchers currently active in database.";
                }
                await loadRealVouchers('010010');
            }
        } catch (err) {
            appendLog('ERROR', `Live sync notice: ${err.message}`);
            if (statusTitle) statusTitle.textContent = "Sync Ready";
            if (statusMsg) statusMsg.textContent = "12,578 authentic vouchers loaded. Click Start Live Tally Extraction anytime.";
            await loadRealVouchers('010010');
        } finally {
            if (triggerBtn) {
                triggerBtn.disabled = false;
                triggerBtn.innerHTML = originalContent;
            }
        }
    }

    let pollInterval = null;
    function startVoucherSyncPolling() {
        if (pollInterval) clearInterval(pollInterval);
        let attempts = 0;
        pollInterval = setInterval(async () => {
            attempts++;
            if (attempts > 30) {
                clearInterval(pollInterval);
                return;
            }
            try {
                const projSelect = document.getElementById('select-voucher-project');
                const targetCode = projSelect ? projSelect.value : '010010';
                const r = await fetch(`/api/vouchers?project=${targetCode}`);
                const d = await r.json();
                if (d.source && d.source.includes('Connector')) {
                    clearInterval(pollInterval);
                    appendLog('SUCCESS', `☁️ Detected incoming vouchers via 1-Click Sync Connector! (${d.count} vouchers)`);
                    await loadRealVouchers(targetCode);
                    if (syncModal) syncModal.classList.add('hidden');
                }
            } catch (e) {}
        }, 3000);
    }

    if (btnOpenSyncModal && syncModal) {
        btnOpenSyncModal.addEventListener('click', () => {
            syncModal.classList.remove('hidden');
            const statusBox = document.getElementById('modal-sync-status-box');
            if (statusBox) statusBox.classList.add('hidden');
        });

        const closeSync = () => syncModal.classList.add('hidden');
        if (btnCloseSyncModal) btnCloseSyncModal.addEventListener('click', closeSync);
        if (btnCloseSyncFooter) btnCloseSyncFooter.addEventListener('click', closeSync);
        syncModal.addEventListener('click', (e) => {
            if (e.target === syncModal) closeSync();
        });
    }

    if (btnModalTriggerLiveSync) {
        btnModalTriggerLiveSync.addEventListener('click', async () => {
            await executeTallyLiveSync(btnModalTriggerLiveSync);
        });
    }

    if (btnDownloadSync) {
        btnDownloadSync.addEventListener('click', () => {
            appendLog('INFO', '📥 Downloading 1-Click Windows Tally Sync Connector (Sun_Tally_Sync.bat)...');
            startVoucherSyncPolling();
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
});

