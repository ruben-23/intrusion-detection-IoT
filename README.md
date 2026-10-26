# Edge IDS pentru Rețele IoT: Sistem Inteligent de Detecție a Intruziunilor

## 1. Descrierea scenariului

Proiectul urmărește construirea unui sistem IoT distribuit pentru detecția și izolarea automată a atacurilor cibernetice (botnet-uri precum Mirai, DoS, Reconnaissance) direct la marginea rețelei (Edge Computing).

Sistemul colectează fluxuri de rețea simulate de la dispozitive periferice, le trimite către un Edge Gateway care agregă datele în ferestre glisante și rulează un model de Machine Learning optimizat. Dacă se detectează un atac, gateway-ul izolează autonom dispozitivul compromis și raportează alerta către o platformă cloud. Un tablou de bord permite vizualizarea incidentelor, iar un agent inteligent oferă suport decizional.


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

---
- [ ] În prima fază a proiectului, dispozitivele IoT vor reda caracteristicile (features) din dataset gata agregate. 
- [ ] Inițial vor fi utilizate doar 1 sau 2 tipuri de atacuri pentru antrenare și testare.
---

### Obiective opționale

- [ ] Rularea proceselor pe calculatoare fizice distincte (ex. 3x Raspberry Pi + 1x Server Linux).
- [ ] Reconstruirea requesturile din traficul original (brut) capturat în timpul atacurilor, renunțând la caracteristicile gata agregate.
- [ ] Extinderea sistemului prin adăugarea opțională a celorlalte tipuri de atacuri disponibile în dataset.
- [ ] Implementarea unui broker MQTT (Mosquitto) pentru comunicația hibridă.
- [ ] Optimizarea modelului ML în format ONNX pentru latențe de sub 5 ms.

### Obiectiv AI / LLM 

Integrarea unui asistent conversațional folosind **Model Context Protocol (MCP)** și **GraphRAG**.

Exemple:
- „De ce a fost izolat dispozitivul Camera_01 astăzi la ora 14:10?”
- „Afișează istoricul atacurilor de tip DoS din ultimele 24 de ore.”



---
## 3. Arhitectura propusă

Fluxul de date este structurat pe 5 procese Python independente:

**Dispozitive Periferice → Edge Gateway (IDS) → Cloud/Backend → Frontend & Agent**

| Componentă | Responsabilitate |
|---|---|
| **Dispozitiv (RPi 2/3)** | Redă fluxuri din CICIoT2023 (Benign/Atac) și ascultă comenzi. |
| **Gateway (RPi 1)** | Multiplexare asincronă, extragere features, Edge AI, actuare (firewall). |
| **Backend (Server)** | API FastAPI, validare Pydantic, expunere WebSockets, broker MQTT. |
| **Stocare (Server)** | DB Serii de timp (metrici) + Graf de cunoștințe (Topologie & Taxonomie atacuri). |
| **Frontend (Laptop)** | Streamlit Dashboard (harta rețelei, grafice live) și consola LLM. |

---
## 4. Dataset utilizat

Proiectul utilizează **CICIoT2023**, un dataset standardizat ce conține trafic IoT generat de dispozitive reale aflate sub diverse categorii de atac cibernetic.

* **Caracteristici:** 46 de metrici statistice de rețea (ex. pachete/secundă, mărime medie, flag-uri TCP). 

    *Notă: În prima fază, dispozitivele vor transmite direct aceste caracteristici gata agregate.*
* **Clase:** Benign + 7 categorii de atac (Mirai, DoS, DDoS, Recon, Web, Brute Force, Spoofing). 
    
    *Notă: În etapa inițială (MVP) se vor folosi doar 1-2 tipuri de atacuri, restul putând fi activate opțional ulterior.*


---
## 5. Identificarea anomaliilor (Edge AI)

**Mecanismul de detecție:** Model de Machine Learning (LightGBM/Random Forest) antrenat pe datele CICIoT2023

### Pașii de procesare la margine:

1. Pachetele intră într-o coadă circulară (buffer RAM cu limită strictă per dispozitiv).

2. La fiecare secundă (fereastră glisantă), se extrage vectorul cu cele 46 de caracteristici (sau se citește direct vectorul agregat, în prima fază a proiectului).

3. Dacă modelul returnează o clasă de atac (ex. `Mirai`), Gateway-ul aruncă pachetele, taie conexiunea socket și raportează alerta.

---


## 6. Integrare LLM (GraphRAG & MCP)

Agentul nu doar răspunde la întrebări, ci și analizează cauza incidentelor:

1. Utilizatorul pune o întrebare în interfață.

2. LLM-ul apelează unelte expuse prin **Model Context Protocol (MCP)** pentru a interoga baza de date de serii de timp.

3. Sistemul consultă graful de cunoștințe (**GraphRAG**) pentru a compara comportamentul așteptat al dispozitivului cu semnătura atacului (Mirai, DoS).

4. Răspunsul este fundamentat strict pe datele rețelei și taxonomiile din CICIoT2023, fiind afișat în panou.


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

## 8. Referințe 


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
