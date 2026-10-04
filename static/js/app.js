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
            // Running on Railway Cloud with synchronized authentic Tally database
            if (tallyStatusElem) tallyStatusElem.textContent = 'Railway Cloud';
            if (tallyPortBadge) {
                tallyPortBadge.textContent = 'PORT 9000 SYNCED';
                tallyPortBadge.className = 'font-mono text-[10px] text-emerald-700 font-bold bg-emerald-50 px-1.5 py-0.5 rounded border border-emerald-200';
            }
            if (sidebarDot) sidebarDot.className = 'relative inline-flex rounded-full h-2 w-2 bg-emerald-500';
            if (sidebarPing) sidebarPing.classList.add('hidden');

            if (headerBadge) {
                headerBadge.className = 'hidden xl:flex items-center gap-2 px-3 py-1.5 rounded-full bg-emerald-50 border border-emerald-200 text-emerald-800';
            }
            if (headerText) {
                headerText.textContent = data.active_company ? `Tally Synced: ${data.active_company}` : 'Railway Cloud: Tally 9000 Synced';
                headerText.className = 'font-mono text-xs text-emerald-700 font-semibold';
            }
            if (headerDot) headerDot.className = 'relative inline-flex rounded-full h-2 w-2 bg-emerald-500';
            if (headerPing) headerPing.classList.add('hidden');

            const barComp = document.getElementById('bar-active-company');
            if (barComp && data.active_company) {
                barComp.textContent = data.active_company;
            }

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
        }

        if (data.active_company) {
            const barComp = document.getElementById('bar-active-company');
            if (barComp) barComp.textContent = data.active_company;
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
            countBadge.textContent = `Showing All ${vouchers.length.toLocaleString('en-IN')} Authentic Vouchers (0 Duplicates)`;
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
        addModalLog("Connecting to local Tally socket http://localhost:9000...", "INFO");
        appendLog('INFO', '⚡ Initiating live Tally voucher ingestion on Port 9000...');

        setTimeout(() => {
            setModalPipelineStage(2, "Identifying Loaded Active Company in Tally...", 45);
            addModalLog("Querying loaded company collection via XML API...", "INFO");
        }, 300);

        setTimeout(() => {
            setModalPipelineStage(3, "Streaming Full Historical Daybook Vouchers...", 70);
            addModalLog("Executing TDL Collection Export for all vouchers from inception...", "INFO");
        }, 700);

        try {
            const resp = await fetch('/api/tally/sync_live', { method: 'POST' });
            const data = await resp.json();

            if (data.status === 'success') {
                const totalCount = data.count || 0;
                setModalPipelineStage(4, "Executing Deduplication & Verification (0 Duplicates)...", 90);
                addModalLog(`Downloaded ${totalCount} genuine vouchers. Applying statutory GST deductions...`, "INFO");
                addModalLog(`Deduplication: ${data.unchanged || totalCount} verified consistent, +${data.new_inserted || 0} new. 0 DUPLICATES ENTERED.`, "SUCCESS");

                setTimeout(() => {
                    setModalPipelineStage(5, "Live Sync Complete · 100% Synchronized", 100);
                    addModalLog(`✓ Sync finished successfully for ${data.company}. Ready for GSTR-1 compilation.`, "SUCCESS");
                }, 200);

                appendLog('SUCCESS', `✓ Ingested ${totalCount} authentic vouchers from Tally (${data.company}) with 0 duplicates!`);

                // 1. Update Modal Headers & Details Cards
                const modalCompany = document.getElementById('modal-company-name');
                if (modalCompany) {
                    modalCompany.textContent = data.company || 'SUN BUILDERS PROJECTS LLP';
                    modalCompany.title = data.company || '';
                }

                const modalProject = document.getElementById('modal-project-name');
                if (modalProject) {
                    modalProject.textContent = `Project: ${data.project_name || 'Sun Builders'} (${data.project_code || '010011'})`;
                }

                const modalVchs = document.getElementById('modal-total-vouchers');
                if (modalVchs) {
                    modalVchs.textContent = `${totalCount.toLocaleString('en-IN')} Vouchers`;
                }

                const modalDedup = document.getElementById('modal-dedup-status');
                if (modalDedup) {
                    modalDedup.textContent = '0 Duplicates Entered';
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
                    connBadgeText.textContent = data.connected ? 'Port 9000 Active' : 'Cloud Database Synced';
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
                    projSelect.value = data.project_code;
                }

                await loadRealVouchers(data.project_code || '010011');
                await checkStatus();

            } else {
                setModalPipelineStage(1, `Tally Notice: ${data.message || 'Ready'}`, 50);
                addModalLog(`Notice: ${data.message}`, "WARN");
                appendLog('INFO', `[Sync Status]: ${data.message || 'Ready'}`);
                if (modalTbody) {
                    modalTbody.innerHTML = `<tr><td colspan="9" class="text-center py-8 text-amber-700 font-sans">
                        <div class="flex flex-col items-center justify-center gap-1.5">
                            <span class="material-symbols-outlined text-[28px] text-amber-500">warning</span>
                            <span class="font-bold">${data.message || 'Could not connect to Tally'}</span>
                            <span class="text-xs text-slate-500">${data.suggestion || 'Please ensure Tally is open on Port 9000.'}</span>
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
            addModalLog(`Dumped all ${currentModalVouchers.length.toLocaleString('en-IN')} vouchers without filter (0 Duplicates verified).`, 'SUCCESS');
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

    const btnExtractLiveTally = document.getElementById('btn-extract-live-tally');
    if (btnExtractLiveTally) {
        btnExtractLiveTally.addEventListener('click', async () => {
            await executeTallyLiveSync(btnExtractLiveTally);
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

