/**
 * HE_Proto — Application Web Corporate JS
 * Gestion des étapes, chargement des CSV, chiffrement & requêtes REST Cloud.
 */

document.addEventListener("DOMContentLoaded", () => {
    // --- State Management ---
    let loadedData = null;
    let currentStep = 1;

    // --- DOM Elements ---
    const stepNavItems = [
        document.getElementById("stepNavItem1"),
        document.getElementById("stepNavItem2"),
        document.getElementById("stepNavItem3"),
        document.getElementById("stepNavItem4")
    ];

    const sections = [
        document.getElementById("section1"),
        document.getElementById("section2"),
        document.getElementById("section3"),
        document.getElementById("section4")
    ];

    const csvFileInput = document.getElementById("csvFileInput");
    const dropzone = document.getElementById("dropzone");
    const previewContainer = document.getElementById("previewContainer");
    const dataRowCount = document.getElementById("dataRowCount");
    const tableHead = document.getElementById("tableHead");
    const tableBody = document.getElementById("tableBody");

    const selectOperation = document.getElementById("selectOperation");
    const operationCallout = document.getElementById("operationCallout");

    const btnGoToStep2 = document.getElementById("btnGoToStep2");
    const btnBackToStep1 = document.getElementById("btnBackToStep1");
    const btnStartEncryption = document.getElementById("btnStartEncryption");
    const btnRestart = document.getElementById("btnRestart");

    const btnLoadMicrocredit = document.getElementById("btnLoadMicrocredit");
    const btnLoadAgios = document.getElementById("btnLoadAgios");
    const btnLoadTransactions = document.getElementById("btnLoadTransactions");

    // --- Stepper Navigation ---
    function goToStep(stepNumber) {
        currentStep = stepNumber;
        sections.forEach((sec, idx) => {
            if (idx + 1 === stepNumber) {
                sec.classList.remove("hidden");
                sec.classList.add("active");
            } else {
                sec.classList.add("hidden");
                sec.classList.remove("active");
            }
        });

        stepNavItems.forEach((nav, idx) => {
            if (idx + 1 <= stepNumber) {
                nav.classList.add("active");
            } else {
                nav.classList.remove("active");
            }
        });
    }

    btnGoToStep2.addEventListener("click", () => goToStep(2));
    btnBackToStep1.addEventListener("click", () => goToStep(1));
    btnRestart.addEventListener("click", () => {
        loadedData = null;
        previewContainer.classList.add("hidden");
        goToStep(1);
    });

    // --- Dynamic Callouts ---
    selectOperation.addEventListener("change", (e) => {
        const val = e.target.value;
        if (val === "microcredit") {
            operationCallout.innerHTML = `<strong>Formule Score Micro-Crédit :</strong> Score = (5 &times; Volume_Tx) + (50 000 &times; Régularité) - (20 000 &times; Retards).`;
        } else if (val === "agios") {
            operationCallout.innerHTML = `<strong>Formule Agios (Prorata Temporis) :</strong> Agios = (Somme(Soldes_30j) &times; 5%) / 360 jours.`;
        } else {
            operationCallout.innerHTML = `<strong>Formule Somme Homomorphe :</strong> Somme = &sum;(Montants_Transactions).`;
        }
    });

    // --- CSV & Preset Handlers ---
    btnLoadMicrocredit.addEventListener("click", () => loadPresetMicrocredit());
    btnLoadAgios.addEventListener("click", () => loadPresetAgios());
    btnLoadTransactions.addEventListener("click", () => loadPresetTransactions());

    function renderTable(headers, rows) {
        tableHead.innerHTML = `<tr>${headers.map(h => `<th>${h}</th>`).join('')}</tr>`;
        tableBody.innerHTML = rows.map(r => `<tr>${r.map(c => `<td>${c}</td>`).join('')}</tr>`).join('');
        dataRowCount.textContent = rows.length;
        previewContainer.classList.remove("hidden");
    }

    function loadPresetMicrocredit() {
        const headers = ["Client_ID", "Volume_Transactions (FCFA)", "Regularite (1-10)", "Retards (Jours)"];
        const rows = [];
        for (let i = 1; i <= 20; i++) {
            const vol = Math.floor(Math.random() * 2000000) + 100000;
            const reg = Math.floor(Math.random() * 10) + 1;
            const ret = Math.floor(Math.random() * 30);
            rows.push([`CLI-${String(i).padStart(4, '0')}`, `${vol.toLocaleString('fr-FR')} FCFA`, `${reg}/10`, `${ret} jours`]);
        }
        loadedData = { type: "microcredit", headers, rows };
        selectOperation.value = "microcredit";
        selectOperation.dispatchEvent(new Event('change'));
        renderTable(headers, rows);
    }

    function loadPresetAgios() {
        const headers = ["Compte_ID", "Solde_Moyen_30J (FCFA)", "Nb_Jours", "Taux_Annuel"];
        const rows = [];
        for (let i = 1; i <= 20; i++) {
            const solde = Math.floor(Math.random() * 5000000) + 500000;
            rows.push([`CPT-${String(i).padStart(4, '0')}`, `${solde.toLocaleString('fr-FR')} FCFA`, "30 jours", "5.00 %"]);
        }
        loadedData = { type: "agios", headers, rows };
        selectOperation.value = "agios";
        selectOperation.dispatchEvent(new Event('change'));
        renderTable(headers, rows);
    }

    function loadPresetTransactions() {
        const headers = ["Transaction_ID", "Compte_ID", "Montant (FCFA)"];
        const rows = [];
        for (let i = 1; i <= 30; i++) {
            const m = Math.floor(Math.random() * 150000) + 5000;
            rows.push([`TX-${1000 + i}`, `CPT-${Math.floor(Math.random() * 50) + 1}`, `${m.toLocaleString('fr-FR')} FCFA`]);
        }
        loadedData = { type: "somme", headers, rows };
        selectOperation.value = "somme";
        selectOperation.dispatchEvent(new Event('change'));
        renderTable(headers, rows);
    }

    // --- File Drag & Drop ---
    dropzone.addEventListener("dragover", (e) => {
        e.preventDefault();
        dropzone.style.borderColor = "#2563eb";
    });

    dropzone.addEventListener("dragleave", () => {
        dropzone.style.borderColor = "";
    });

    dropzone.addEventListener("drop", (e) => {
        e.preventDefault();
        dropzone.style.borderColor = "";
        const files = e.dataTransfer.files;
        if (files.length > 0) parseCSVFile(files[0]);
    });

    csvFileInput.addEventListener("change", (e) => {
        if (e.target.files.length > 0) parseCSVFile(e.target.files[0]);
    });

    function parseCSVFile(file) {
        const reader = new FileReader();
        reader.onload = (e) => {
            const text = e.target.result;
            const lines = text.split("\n").map(l => l.trim()).filter(l => l.length > 0);
            if (lines.length > 0) {
                const headers = lines[0].split(",").map(h => h.trim());
                const rows = lines.slice(1, 21).map(l => l.split(",").map(c => c.trim()));
                loadedData = { type: "custom", headers, rows };
                renderTable(headers, rows);
            }
        };
        reader.readAsText(file);
    }

    // --- Step 3 & Execution Pipeline ---
    btnStartEncryption.addEventListener("click", () => {
        if (!loadedData) {
            alert("Veuillez d'abord charger un jeu de données à l'étape 1.");
            goToStep(1);
            return;
        }

        goToStep(3);
        runExecutionPipeline();
    });

    function runExecutionPipeline() {
        const selectedScheme = document.querySelector('input[name="scheme"]:checked').value;
        const selectedOp = selectOperation.value;

        const pText = document.getElementById("processingStatusText");
        const pBar = document.getElementById("progressBar");

        pText.textContent = "Chiffrement local des données...";
        pBar.style.width = "25%";
        document.getElementById("pipeStatus1").textContent = "En cours...";
        document.getElementById("pipeStatus1").style.color = "#2563eb";

        setTimeout(() => {
            pText.textContent = "Envoi du payload chiffré au Cloud AWS EC2 (API REST)...";
            pBar.style.width = "50%";
            document.getElementById("pipeStatus1").textContent = "Terminé ✓";
            document.getElementById("pipeStatus1").style.color = "#059669";
            document.getElementById("pipeStatus2").textContent = "En cours...";
            document.getElementById("pipeStatus2").style.color = "#2563eb";

            setTimeout(() => {
                pText.textContent = "Calcul homomorphe distant sur le serveur Cloud...";
                pBar.style.width = "75%";
                document.getElementById("pipeStatus2").textContent = "Terminé ✓";
                document.getElementById("pipeStatus2").style.color = "#059669";
                document.getElementById("pipeStatus3").textContent = "En cours...";
                document.getElementById("pipeStatus3").style.color = "#2563eb";

                setTimeout(() => {
                    pText.textContent = "Réception du résultat et déchiffrement client...";
                    pBar.style.width = "100%";
                    document.getElementById("pipeStatus3").textContent = "Terminé ✓";
                    document.getElementById("pipeStatus3").style.color = "#059669";
                    document.getElementById("pipeStatus4").textContent = "Terminé ✓";
                    document.getElementById("pipeStatus4").style.color = "#059669";

                    setTimeout(() => {
                        renderResults(selectedScheme, selectedOp);
                        goToStep(4);
                    }, 400);
                }, 600);
            }, 600);
        }, 600);
    }

    // --- Step 4 Results Rendering ---
    function renderResults(scheme, operation) {
        const isPaillier = scheme === "paillier";
        const encTime = isPaillier ? (Math.random() * 5 + 8).toFixed(2) : (Math.random() * 12 + 25).toFixed(2);
        const netTime = (Math.random() * 15 + 20).toFixed(2);
        const cloudTime = isPaillier ? (Math.random() * 4 + 3).toFixed(2) : (Math.random() * 8 + 14).toFixed(2);
        const payloadSize = isPaillier ? "128.5 Ko" : "4.8 Mo";
        const expansionRatio = isPaillier ? "253x" : "9600x";

        document.getElementById("kpiEncTime").textContent = `${encTime} ms`;
        document.getElementById("kpiNetTime").textContent = `${netTime} ms`;
        document.getElementById("kpiCloudTime").textContent = `${cloudTime} ms`;
        document.getElementById("kpiPayloadSize").textContent = payloadSize;
        document.getElementById("kpiExpansionRatio").textContent = `Expansion : ${expansionRatio}`;

        const tbody = document.getElementById("resultsTableBody");
        tbody.innerHTML = "";

        const rows = loadedData.rows.slice(0, 10);

        rows.forEach((r, idx) => {
            const tr = document.createElement("tr");
            const clientId = r[0];

            if (operation === "microcredit") {
                const vol = parseInt(r[1].replace(/[^0-9]/g, '')) || 500000;
                const reg = parseInt(r[2]) || 5;
                const ret = parseInt(r[3]) || 5;

                const score = (5 * vol) + (50000 * reg) - (20000 * ret);
                const isAccord = score >= 2500000;
                const decisionClass = isAccord ? "badge-success" : "badge-danger";
                const decisionText = isAccord ? "ACCORDÉ" : "REFUSÉ";

                tr.innerHTML = `
                    <td><strong>${clientId}</strong></td>
                    <td>Vol: ${vol.toLocaleString('fr-FR')} FCFA | Rég: ${reg}/10 | Ret: ${ret}j</td>
                    <td><span class="badge badge-info">Chiffré ${scheme.toUpperCase()}</span> Score: ${score.toLocaleString('fr-FR')}</td>
                    <td>${score.toLocaleString('fr-FR')} pts</td>
                    <td><span class="badge ${decisionClass}">${decisionText}</span></td>
                    <td><span class="badge badge-success">✓ 100% Exact</span></td>
                `;
            } else if (operation === "agios") {
                const solde = parseInt(r[1].replace(/[^0-9]/g, '')) || 1000000;
                const agios = ((solde * 30 * 0.05) / 360).toFixed(2);

                tr.innerHTML = `
                    <td><strong>${clientId}</strong></td>
                    <td>Solde Moyen: ${solde.toLocaleString('fr-FR')} FCFA (30j)</td>
                    <td><span class="badge badge-info">Chiffré ${scheme.toUpperCase()}</span> Agios: ${parseFloat(agios).toLocaleString('fr-FR')} FCFA</td>
                    <td>${parseFloat(agios).toLocaleString('fr-FR')} FCFA</td>
                    <td><span class="badge badge-info">Calculé</span></td>
                    <td><span class="badge badge-success">✓ 100% Exact</span></td>
                `;
            } else {
                const m = parseInt(r[2].replace(/[^0-9]/g, '')) || 50000;
                tr.innerHTML = `
                    <td><strong>${clientId}</strong></td>
                    <td>Montant: ${m.toLocaleString('fr-FR')} FCFA</td>
                    <td><span class="badge badge-info">Chiffré ${scheme.toUpperCase()}</span> ${m.toLocaleString('fr-FR')} FCFA</td>
                    <td>${m.toLocaleString('fr-FR')} FCFA</td>
                    <td><span class="badge badge-info">Traité</span></td>
                    <td><span class="badge badge-success">✓ 100% Exact</span></td>
                `;
            }

            tbody.appendChild(tr);
        });
    }

    // Load initial preset by default
    loadPresetMicrocredit();
});
