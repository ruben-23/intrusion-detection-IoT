# Edge IDS pentru Rețele IoT: Sistem Inteligent de Detecție a Intruziunilor

Barieră inteligentă de securitate la marginea rețelei (Edge Computing) concepută pentru a monitoriza traficul generat de dispozitive IoT, a detecta botnet-uri și intruziuni în timp real și a izola autonom nodurile infectate înainte de propagarea atacului.

Proiectul utilizează setul de date **CICIoT2023** și integrează un pipeline hibrid compus din inferență Edge AI de joasă latență, mecanisme automate de carantină prin firewall și un modul agentic bazat pe **GraphRAG** și **Model Context Protocol (MCP)** pentru audit și explicabilitate în limbaj natural.

---

## Arhitectura Hardware

Sistemul este distribuit pe patru componente hardware distincte:

| Componentă | Hardware | Rol & Responsabilități |
| --- | --- | --- |
| **Dispozitive Periferice** | Raspberry Pi #2 & #3 | Rulează scripturi de replay (`device_node.py`) pentru a reda trafic benign și atacuri simulate (Mirai, DoS, Recon) din CICIoT2023.

 |
| **Gateway & Edge IDS** | Raspberry Pi #1 | Recepție asincronă a pachetelor, gestionare cozi FIFO per dispozitiv, inferență ONNX (< 5 ms) și izolare prin `iptables`.

 |
| **Cloud / Backend** | Server Linux OCI | Broker Mosquitto, API central FastAPI, baze de date pentru serii de timp și stocare pe graf.

 |
| **Consolă Administrator** | Laptop | Tablou de bord în timp real dezvoltat în Streamlit, interfațat cu un asistent LLM pentru investigații.

 |

---

## Fluxul de Prelucrare la Nivel de Gateway

```
[ Dispozitive IoT ] (Raspberry Pi #2 / #3)
         │
         ▼ (Trafic TCP/UDP)
[ 1. Receptie Asincronă & Cozi FIFO per IP ] (device_buffers[ip])
         │
         ▼ (Fereastră glisantă - ex: 1s)
[ 2. Extragere Vector Numeric ] (pachete/s, IAT, dimensiune medie/std, flag-uri TCP)
         │
         ▼ (Inferență locală < 5ms)
[ 3. Model Edge AI (ONNX / Scikit-learn) ]
         │
    ┌────┴───────────────────────────┐
    ▼                                ▼
[ Benign ]                     [ Malițios ]
    │                                ├─ Drop buffer[cite: 6]
    │                                ├─ Blocare IP & socket (`iptables`)[cite: 6, 7]
    ▼                                ▼
Transmisie date normale        Alertă critică JSON către FastAPI[cite: 6, 7]

```

1. **Recepție și Buffer per Nod:** Conexiunile sunt ascultate asincron. Pachetele sunt grupate per IP într-un cache circular de tip FIFO (`device_buffers[ip]`) pentru a preveni epuizarea memoriei în scenarii de DoS.


2. **Fereastră Glisantă & Extragere Statistici:** La fiecare secundă, bufferul generează un vector unidimensional compus din:
* Număr de pachete pe secundă;


* Dimensiunea medie a pachetelor și deviația standard;


* Timpul scurs între pachete (Inter-Arrival Time - IAT);


* Distribuția flag-urilor TCP.




3. **Inferență Edge AI:** Vectorul este clasificat local folosind un model ONNX / Scikit-learn optimizat pentru un timp de răspuns sub 5 ms.


4. **Acțiune și Carantină:**
* **Benign:** Păstrează starea nodului `NORMAL` și transmite metricile agregate către cloud.


* **Malițios:** Golește bufferul afectat, blochează traficul de la IP-ul respectiv prin reguli dinamice de `iptables`, închide socket-ul și notifică backend-ul.





---

## Structura Proceselor Software (Python)

Aplicația este structurată în 5 procese obligatorii, distribuite modular:

| ID | Fișier / Proces | Nod Gazdă | Tehnologii Cheie | Descriere |
| --- | --- | --- | --- | --- |
| **P1** | `device_node.py` | Raspberry Pi #2 & #3 | Sockets UDP/TCP, JSON, `paho-mqtt` | Simulează traficul IoT prin replay din CICIoT2023 și ascultă semnale de oprire.

 |
| **P2** | `gateway_proxy.py` | Raspberry Pi #1 | `asyncio`, ONNX Runtime, `iptables` | Gestionează cozile FIFO, extrage vectorii, execută inferența AI și aplică carantina.

 |
| **P3** | `backend_api.py` | Server Linux OCI | FastAPI, Pydantic, WebSockets | Ingestează alertele JSON, validează datele și propagă evenimentele către dashboard.

 |
| **P4** | `storage_service.py` | Server Linux OCI | TSDB, Graph Database, GraphRAG | Persistă seriile temporale și relațiile de graf pentru audit și context istoric.

 |
| **P5** | `dashboard_app.py` | Laptop Administrator | Streamlit, Model Context Protocol (MCP) | Interfață de vizualizare live și consolă de interogare a incidentelor printr-un agent LLM.

 |

---

## Nivelul Agentic: GraphRAG & MCP

Pentru a depăși limitările alertelor simple bazate pe ID-uri și scoruri brute, sistemul include un asistent capabil să explice deciziile de securitate în limbaj natural direct în Streamlit:

```
[ Operator ] ──> Întrebare: "De ce a fost deconectat nodul Raspberry Pi #2?"
                       │
                       ▼
                 [ Agent LLM ]
                       │
            ┌──────────┴──────────┐
            ▼                     ▼
     [ Server MCP ]        [ GraphRAG ]
     (Alerte & loguri)     (Profiluri noduri & semnături CICIoT2023)
            │                     │
            └──────────┬──────────┘
                       ▼
[ Răspuns Explicativ ]: "Dispozitivul a generat un atac Mirai-SYN_Flood (+300% SYN flags fată de profilul legitim). Carantina a fost aplicată automat."

```

1. **Protocol MCP:** Oferă LLM-ului acces securizat la unelte pentru citirea stării curente, a jurnalelor și a alertelor brute sosite de la Gateway.


2. **GraphRAG:** Interoghează un graf de cunoștințe ce corelează profilul de trafic de bază al fiecărui dispozitiv cu semnăturile atacurilor din setul CICIoT2023.


3. **Explicabilitate:** Rezultatul combină anomaliile observate (ex: deviații de IAT, flood de pachete) cu justificarea blocării IP-ului.



