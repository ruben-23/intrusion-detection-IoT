# Edge IDS pentru Rețele IoT: Sistem Inteligent de Detecție a Intruziunilor

Barieră inteligentă de securitate la marginea rețelei (Edge Computing) concepută pentru a monitoriza traficul generat de dispozitive IoT, a detecta botnet-uri și intruziuni în timp real și a izola autonom nodurile infectate înainte de propagarea atacului.

Proiectul utilizează setul de date **CICIoT2023** și integrează un pipeline hibrid compus din inferență Edge AI de joasă latență, mecanisme automate de carantină prin firewall și un modul agentic bazat pe **GraphRAG** și **Model Context Protocol (MCP)** pentru audit și explicabilitate în limbaj natural.

---
<!-- 
## Arhitectura Hardware

Sistemul este distribuit pe patru componente hardware distincte:

| Componentă | Hardware | Rol & Responsabilități |
| --- | --- | --- |
| **Dispozitive Periferice** | Raspberry Pi #2 & #3 | Rulează scripturi de replay (`device_node.py`) pentru a reda trafic benign și atacuri simulate (Mirai, DoS, Recon) din CICIoT2023.

| **Gateway & Edge IDS** | Raspberry Pi #1 | Recepție asincronă a pachetelor, gestionare cozi FIFO per dispozitiv, inferență ONNX (< 5 ms) și izolare prin `iptables`.

 |
| **Cloud / Backend** | Server Linux OCI | Broker Mosquitto, API central FastAPI, baze de date pentru serii de timp și stocare pe graf.

 |
| **Consolă Administrator** | Laptop | Tablou de bord în timp real dezvoltat în Streamlit, interfațat cu un asistent LLM pentru investigații.

 | -->



## Arhitectura Hardware

Sistemul este distribuit pe patru componente hardware distincte:
| Componentă | Hardware | Rol și responsabilități |
|---|---|---|
| **Dispozitive periferice** | Raspberry Pi #2 și #3 | Rulează scripturile de replay (`device_node.py`) pentru a reproduce trafic benign și atacuri simulate (Mirai, DoS, Recon) din setul de date CICIoT2023. |
| **Gateway și Edge IDS** | Raspberry Pi #1 | Asigură recepția asincronă a pachetelor, gestionarea cozilor FIFO per dispozitiv, inferența ONNX (sub 5 ms) și izolarea dispozitivelor prin `iptables`. |
| **Cloud / Backend** | Server Linux OCI | Găzduiește brokerul Mosquitto, API-ul central bazat pe FastAPI, bazele de date pentru serii temporale și sistemul de stocare a datelor sub formă de graf. |
| **Consolă administrator** | Laptop | Oferă un tablou de bord în timp real, dezvoltat cu Streamlit, integrat cu un asistent LLM pentru investigații. |

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
<!-- 
## Structura Proceselor Software (Python)

Aplicația este structurată în 5 procese obligatorii, distribuite modular:

| ID | Fișier / Proces | Nod gazdă | Tehnologii cheie | Descriere |
|---|---|---|---|---|
| **P1** | `device_node.py` | Raspberry Pi #2 și #3 | Sockets UDP/TCP, JSON, `paho-mqtt` | Simulează traficul IoT prin replay din CICIoT2023 și ascultă semnalele de oprire. |
| **P2** | `gateway_proxy.py` | Raspberry Pi #1 | `asyncio`, ONNX Runtime, `iptables` | Gestionează cozile FIFO, extrage vectorii de caracteristici, execută inferența AI și aplică măsurile de carantină. |
| **P3** | `backend_api.py` | Server Linux OCI | FastAPI, Pydantic, WebSockets | Primește alertele în format JSON, validează datele și propagă evenimentele către dashboard. |
| **P4** | `storage_service.py` | Server Linux OCI | TSDB, Graph Database, GraphRAG | Persistă seriile temporale și relațiile din graf pentru audit și acces la contextul istoric. |
| **P5** | `dashboard_app.py` | Laptop administrator | Streamlit, Model Context Protocol (MCP) | Oferă o interfață pentru vizualizarea în timp real și o consolă pentru interogarea incidentelor prin intermediul unui agent LLM. |
--- -->

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

--- 

## Referințe 


1. [IoT Security: Risks, Challenges, and Best Practices in Securing the IoT](https://www.digi.com/blog/post/iot-security)
2. [Intrusion Detection in IoT](https://www.speranzainc.com/intrusion-detection-in-iot/)

3. [Intrusion Detection in the Internet of Things: A Comprehensive Review of Techniques, Architectures, Datasets, and Emerging Trends](https://www.mdpi.com/1424-8220/26/11/3405)
4. [IoT Security: A Comprehensive Review of Architectures, Threat Models, Detection Methods, and Countermeasures](https://www.mdpi.com/1999-5903/18/5/266)
5. [A survey on intrusion detection system in IoT networks](https://www.sciencedirect.com/science/article/pii/S2772918424000481)
6.  [Bringing IoT Intrusion Detection to the Edge
](https://dl.acm.org/doi/10.1145/3726122.3726166)
7. [An IoT intrusion detection framework based on feature selection and large language models fine-tuning](https://www.nature.com/articles/s41598-025-08905-3)
8. [Intrusion Detection in IoT: A Comprehensive Review of Techniques, Challenges, and Future Directions](https://ieeexplore.ieee.org/document/11137243)
9. [Intrusion Detection on the Internet of Things: A Comprehensive Review and Gap Analysis Toward Real-Time, Lightweight, Adaptive, and Autonomous Security](https://www.mdpi.com/2624-831X/7/1/16)
10.  [Robustness Analysis of Machine Learning Models for IoT Intrusion Detection Under Data Poisoning Attacks](https://arxiv.org/abs/2604.14444)
