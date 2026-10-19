

# 🛡️ Edge-Centric Intrusion Detection & Autonomous Botnet Mitigation

### Mini-aplicație IoT – Sistem inteligent de securitate la marginea rețelei (Edge IDS)

**Echipă:** SecurIoT Team
**Membri:** Student 1, Student 2, Student 3
**Repository GitHub:** `https://github.com/organizatie/edge-botnet-ids` (exemplu)
**Scenariu:** Smart Building / IoT Security: 
**Status:** Propunere / Arhitectură de bază

---

## 1. Descrierea scenariului

Proiectul urmărește construirea unui sistem IoT distribuit pentru detecția și izolarea automată a atacurilor cibernetice (botnet-uri precum Mirai, DoS, Reconnaissance) direct la marginea rețelei (Edge Computing).

Sistemul colectează fluxuri de rețea simulate de la dispozitive periferice, le trimite către un Edge Gateway care agregă datele în ferestre glisante și rulează un model de Machine Learning optimizat. Dacă se detectează un atac, gateway-ul izolează autonom dispozitivul compromis și raportează alerta către o platformă cloud. Un tablou de bord permite vizualizarea incidentelor, iar un agent inteligent oferă suport decizional.

---

**Întrebarea principală:**  *Cum poate un gateway IoT să detecteze și să izoleze autonom un dispozitiv infectat cu malware (ex. Mirai) în mai puțin de 5 milisecunde, reducând dependența de cloud și prevenind colapsul rețelei interne?*

---

## 2. Obiectivele proiectului

### Obiective obligatorii (MVP)

- [ ] Simularea a minimum 2 senzori/dispozitive IoT care redau trafic din setul de date CICIoT2023.
- [ ] Transmiterea asincronă a datelor către un Edge Gateway.
- [ ] Calcularea metricilor de rețea pe ferestre glisante (sliding windows) la nivel edge.
- [ ] Executarea inferenței Edge AI pentru clasificarea traficului (Benign vs. Malițios).
- [ ] Izolarea automată a traficului (drop socket / iptables) în caz de anomalie.
- [ ] Transmiterea alertelor structurate către un backend REST/FastAPI.
- [ ] Dezvoltarea unui dashboard în Streamlit pentru monitorizarea live.

### Obiective opționale / Avansate (Nota B)

- [ ] Rularea proceselor pe calculatoare fizice distincte (ex. 3x Raspberry Pi + 1x Server Linux).
- [ ] Implementarea unui broker MQTT (Mosquitto) pentru comunicația hibridă.
- [ ] Optimizarea modelului ML în format ONNX pentru latențe de sub 5 ms.

### Obiectiv AI / LLM (Nota C)

Integrarea unui asistent conversațional (SOC Analyst) folosind **Model Context Protocol (MCP)** și **GraphRAG**.

Exemple:
- „De ce a fost izolat dispozitivul Camera_01 astăzi la ora 14:10?”
- „Ce tipar de atac a declanșat regula de firewall pe senzorul de acces?”
- „Afișează istoricul atacurilor de tip Mirai din ultimele 24 de ore.”

*Răspunsurile vor fi generate prin corelarea profilului legitim al dispozitivului (din graful de cunoștințe) cu ferestrele de telemetrie anormale, nu din halucinații LLM.*
---

## 3. Arhitectura propusă

Fluxul de date este structurat pe 5 procese Python independente:

**Dispozitive Periferice → Edge Gateway (IDS) → Cloud/Backend → Frontend & Agent**

| Componentă | Responsabilitate |
|---|---|
| **Dispozitiv (RPi 2/3)** | Redă fluxuri din CICIoT2023 (Benign/Atac) via `replay.py` și ascultă comenzi. |
| **Gateway (RPi 1)** | Multiplexare asincronă, extragere features, Edge AI (ONNX), actuare (firewall). |
| **Backend (Server)** | API FastAPI, validare Pydantic, expunere WebSockets, broker MQTT. |
| **Stocare (Server)** | DB Serii de timp (metrici) + Graf de cunoștințe (Topologie & Taxonomie atacuri). |
| **Frontend (Laptop)** | Streamlit Dashboard (harta rețelei, grafice live) și consola LLM. |

**Schița arhitecturii:**

```text
[IP Camera Node] ────┐ (Benign + Mirai)
                     │
[Smart Sensor Node] ─┼──► [Edge Gateway IDS] ────(Drop / iptables)
                     │          │
                     │          │ REST / MQTT / gRPC
                     │          ▼
                     │    [Cloud Backend]
                     │    ├── FastAPI REST
                     │    ├── Time-Series DB
                     │    └── Knowledge Graph
                     │          │
                     │          ▼
                     │    [Web Dashboard]
                     │    ├── Network Topology
                     │    ├── Live Bandwidth
                     │    └── Security Alerts
                     │
              [LLM Agent / SOC Assistant] (via MCP)

```

---

## 4. Datele și simularea senzorilor

### Dataset utilizat

Proiectul utilizează **CICIoT2023**, un dataset standardizat ce conține trafic IoT generat de dispozitive reale aflate sub diverse categorii de atac cibernetic.

* **Caracteristici:** 46 de metrici statistice de rețea (ex. pachete/secundă, mărime medie, flag-uri TCP).

* **Clase:** Benign + 7 categorii de atac (Mirai, DoS, DDoS, Recon, Web, Brute Force, Spoofing).

### Exemplu de Alertă JSON transmisă către Backend

```json
{
  "event_type": "security_alert",
  "device_id": "camera_01",
  "ip_address": "192.168.1.101",
  "threat_detection": {
    "predicted_attack": "Mirai-SYN_Flood",
    "confidence_score": 0.987
  },
  "traffic_anomalies": {
    "measured_pps": 8420.0,
    "dominant_flags": "SYN_ONLY",
    "target_port": 23
  },
  "actuation": "iptables -A INPUT -s 192.168.1.101 -j DROP"
}

```

### Generarea datelor

Scriptul `replay.py` citește subseturi extrase din CICIoT2023 și emite pachetele la intervalele originale (sau accelerate), comutând dinamic de la profilul normal la cel de botnet.

---

## 5. Identificarea anomaliilor (Edge AI)

**Mecanismul de detecție:** Model de Machine Learning (LightGBM/Random Forest) antrenat pe datele CICIoT2023 și exportat în **ONNX Runtime** pentru execuție ultrarapidă direct pe procesorul ARM al Gateway-ului.

### Pașii de procesare la margine:

1. Pachetele intră într-o coadă circulară (buffer RAM cu limită strictă per dispozitiv).

2. La fiecare secundă (fereastră glisantă), se extrage vectorul cu cele 46 de caracteristici.

3. Dacă modelul returnează o clasă de atac (ex. `Mirai`), Gateway-ul aruncă pachetele, taie conexiunea socket și raportează alerta.

---

## 6. Interfața frontend – schiță preliminară

Aplicația (Streamlit) funcționează ca un panou de securitate (SOC) pentru administrator.

**Wireframe orientativ:**

```text
+--------------------------------------------------+
|           EDGE IDS SECURITY DASHBOARD            |
+--------------------------------------------------+
| Nodes Active | Blocked Nodes | Bandwidth Usage   |
|      3       |       1       |    12.4 MB/s      |
+--------------------------------------------------+
| NETWORK TOPOLOGY                                 |
|  [Gateway] --- [Node 1 (OK)]                     |
|            \-- [Node 2 (QUARANTINED - RED)]      |
+--------------------------------------------------+
| REAL-TIME TRAFFIC (Packets/Second)               |
|  [         LINE CHART (Node 2 Spiking)         ] |
+--------------------------------------------------+
| ALERT FEED                                       |
| 14:10 | Node 2 | Mirai SYN Flood | ACTION: DROP  |
+--------------------------------------------------+
| AI SOC ANALYST (GraphRAG)                        |
| > De ce a fost blocat Node 2?                    |
| AI: Node 2 (Cameră IP) a depășit profilul normal |
| generând 8420 pachete/sec pe portul 23 (Telnet). |
+--------------------------------------------------+

```

---

## 7. Tehnologii și API-uri

| Componentă | Tehnologie propusă |
| --- | --- |
| Edge ML Runtime | Scikit-learn, ONNX Runtime |
| Gateway Concurrency | Python `asyncio`<br> |
| IoT Messaging | Sockets UDP/TCP, Paho MQTT |
| Backend & API | FastAPI, Uvicorn, Pydantic |
| Baze de Date | SQLite/InfluxDB + Neo4j (Graf) |
| Frontend | Streamlit, WebSockets |
| Integrare LLM | MCP Server (Python), OpenAI/Local API |
| Actuare OS | iptables (Linux Firewall) |

---

## 8. Integrare LLM – Extensie de Excelență (GraphRAG & MCP)

Agentul nu doar răspunde la întrebări, ci și analizează cauza incidentelor:

1. Utilizatorul pune o întrebare în interfață.

2. LLM-ul apelează unelte expuse prin **Model Context Protocol (MCP)** pentru a interoga baza de date de serii de timp.

3. Sistemul consultă graful de cunoștințe (**GraphRAG**) pentru a compara comportamentul așteptat al dispozitivului cu semnătura atacului (Mirai, DoS).

4. Răspunsul este fundamentat strict pe datele rețelei și taxonomiile din CICIoT2023, fiind afișat în panou.

---

<!-- ## 9. Etape de implementare (sprinturi)

| Livrabil | Termen | Activități principale | Livrabil |
| --- | --- | --- | --- |
| **L1**<br> | Săpt. 3 | `replay.py` trimite pachete CICIoT2023 prin UDP/TCP către serverul socket; Fișa Use Case

 | Comunicație de bază |
| **L2**<br> | Săpt. 5 | Gateway asincron multi-client (`asyncio`); Machetă Streamlit

 | Gateway concurent |
| **L3**<br> | Săpt. 8 | Integrare MQTT (Mosquitto), backend FastAPI, WebSockets; Arhitectura

 | Servicii hibride |
| **L4**<br> | Săpt. 10 | Bază de date; antrenare model CICIoT2023 în Colab, export ONNX și rulare pe Gateway

 | Edge AI funcțional |
| **L5**<br> | Săpt. 13 | Integrare agent LLM (MCP + GraphRAG), testare distribuită, Articol IEEE

 | Proiect final complet | -->

---

<!-- ## 10. Repartizarea responsabilităților

| Membru | Responsabilități principale |
| --- | --- |
| **Student 1** | Scripturi `replay.py`, Gateway asincron, modul actuare (`iptables`).

 |
| **Student 2** | Preprocesare CICIoT2023, Antrenare model, FastAPI Backend și Baza de date.

 |
| **Student 3** | Frontend Streamlit, WebSockets, integrare Agent LLM (MCP și GraphRAG).

 | -->

---

## 11. Structura preliminară a repository-ului

```text
edge-botnet-ids/
├── README.md
├── data/                  # Subseturi extrase din CICIoT2023
├── models/                # Modelul clasificator în format .onnx
├── device/                # device_node.py (Redare simulată)
├── gateway/               # gateway_proxy.py (Async, Extragere, Inferență)
├── backend/               # backend_api.py (FastAPI, DB)
├── agent/                 # Servere MCP și scripturi GraphRAG
└── frontend/              # dashboard_app.py (Streamlit)
```

---

## 12. Testare și criterii de succes

Scenariul de demonstrare a succesului (End-to-End):

1. Nodurile RPi #2 și #3 transmit telemetrie normală; interfața este verde (Benign).

2. Pe RPi #2 se comută scriptul pe fișierul de atac Mirai SYN Flood.

3. Gateway-ul detectează anomalia în sub 5 ms prin evaluarea celor 46 de caracteristici statistice.

4. Gateway-ul blochează autonom pachetele și adresa IP, prevenind răspândirea atacului.

5. Backend-ul primește alerta, iar interfața vizuală indică nodul carantinat.

6. Operatorul obține explicații clare de la asistentul inteligent despre specificul atacului respins.

---

## 13. Riscuri și limitări

* Rularea inferenței pe calculatoare single-board (Raspberry Pi) necesită optimizarea strictă a memoriei (ferestre glisante cu limită FIFO) pentru a evita epuizarea RAM-ului.

* Setul de date CICIoT2023 trebuie prelucrat masiv în prealabil (sub-eșantionare din cei 13 GB inițiali).

* Actuarea OS (`iptables`) necesită privilegii ridicate de rețea pe mașina fizică Gateway.

---

## 14. Întrebări deschise

* Care este mărimea optimă a ferestrei glisante (ex. 1 sec, 5 sec) pentru a maximiza detecția atacurilor Low-Rate DoS?

* Ce politici de evacuare a memoriei cache vor fi folosite în cazul în care atacatorul variază dinamic IP-urile sursă (Spoofing)?

* Care model optimizat (LightGBM, Random Forest, Autoencoder) oferă cel mai bun raport acuratețe/latență la exportul în ONNX?
