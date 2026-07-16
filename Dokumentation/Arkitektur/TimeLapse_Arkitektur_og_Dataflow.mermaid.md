# TimeLapse Pro — Arkitektur & Dataflow (Mermaid)

**Dato:** 2026-07-15 · **Forfatter:** Claude (Cowork) · Renderes direkte på GitHub.
Diagrammerne beskriver (1) systemkontekst, (2) dataflow/komponenter, (3) IEC 62443-zoner & miljøer, (4) capture→tag-sekvens og (5) målbilledet: modulær platform/payload. Ret dem sammen med koden — de er versionsstyrede.

> Åbn samme indhold interaktivt i **draw.io/diagrams.net** via `TimeLapse_Arkitektur.drawio` i denne mappe.

---

## 1. Systemkontekst (hvem/hvad taler med systemet)

```mermaid
flowchart TB
    admin([Admin / Operator]):::actor
    kunde([Kunde / Site Manager]):::actor
    tekniker([Servicetekniker]):::actor

    subgraph TLP["TimeLapse Pro"]
        edge["Edge-node<br/>(Orange Pi + kamera)"]:::sys
        headend["Headend<br/>(FastAPI · PostgreSQL · nginx · Ollama)"]:::sys
        ui["Web-UI<br/>(React/Vite)"]:::sys
    end

    gemini["Google Gemini / Vertex AI<br/>(europe-west1, cloud-eskalering)"]:::ext
    crushftp["CrushFTP<br/>(sameksisterer på staging/prod)"]:::ext
    time["NTP / GPS<br/>(tidssynk)"]:::ext

    admin -->|"RBAC + MFA"| ui
    kunde -->|"ser billeder/tags"| ui
    tekniker -->|"lokal provisioning/debug"| edge
    ui --> headend
    edge <-->|"billeder, config, heartbeat, updates"| headend
    headend -->|"AI-eskalering af udvalgte billeder"| gemini
    edge -.->|"tidssynk"| time
    headend -. "deler fysisk maskine, ingen conduit" .- crushftp

    classDef actor fill:#e3f2fd,stroke:#1976d2,color:#0d47a1;
    classDef sys fill:#e8f5e9,stroke:#2e7d32,color:#1b5e20;
    classDef ext fill:#fff3e0,stroke:#ef6c00,color:#e65100;
```

---

## 2. Dataflow & komponenter (det centrale diagram)

```mermaid
flowchart LR
    subgraph EDGE["EDGE-node (felt)"]
        direction TB
        cam["Kamera (Nikon Z30)<br/>gphoto2"]:::c
        relay["Relæ / GPIO<br/>strømstyring"]:::c
        qa["Capture + lokal QA<br/>(NPU / CV: blur, eksponering, WB)"]:::c
        buf["Store-and-forward buffer<br/>(circular)"]:::c
        up["Uploader (SFTP)"]:::c
        ag["Agent (HTTPS)<br/>JWT + HMAC-signering"]:::c
        fp["frame_push<br/>(MJPEG live-view)"]:::c
        tun["Reverse SSH tunnel<br/>(autossh)"]:::c
        hal["HAL<br/>(orangepi/rpi/jetson)"]:::c
        cam --> qa --> buf --> up
        qa --> ag
        relay -. styrer .- cam
    end

    subgraph TRANSP["Transport"]
        direction TB
        t1["SFTP :22222<br/>(billeder)"]:::t
        t2["HTTPS/JWT<br/>(config · heartbeat · updates · metadata)"]:::t
        t3["Reverse SSH<br/>(management-conduit)"]:::t
    end

    subgraph HEAD["HEADEND (Mac Mini)"]
        direction TB
        nginx["nginx (DMZ)<br/>TLS · rate-limit · fail2ban"]:::h
        api["FastAPI (main.py)<br/>RBAC · JWT · MFA"]:::h
        db[("PostgreSQL<br/>captures · camera/customer/site")]:::db
        store[("Storage /Volumes/data-fast<br/>canonical-images + backup")]:::db
        imp["Importer / ingest"]:::h
        ai["AI-tagging<br/>Ollama (lokal) + Gemini (cloud)"]:::h
        cfg["Config-hierarki<br/>global→customer→site→device<br/>(signeret policy-pull)"]:::h
        upd["Update/OTA<br/>signerede artifacts · change tickets · rollback"]:::h
        obs["Observability<br/>SIEM · CMDB · ITIM · node-agent"]:::h
        gdpr["GDPR<br/>redaction · retention · access-log"]:::h
    end

    ui["Web-UI (React/Vite)"]:::u
    gem["Gemini / Vertex AI<br/>(europe-west1, batch)"]:::x

    up --> t1 --> store
    ag --> t2 --> nginx
    tun --> t3 --> nginx
    nginx --> api
    api <--> db
    api --> store
    imp --> db
    store --> imp
    api --> ai --> db
    ai -->|"udvalgte billeder"| gem
    api --> cfg --> t2
    api --> upd --> t2
    api --> obs
    api --> gdpr --> store
    ui --> nginx

    classDef c fill:#e8f5e9,stroke:#2e7d32,color:#1b5e20;
    classDef t fill:#ede7f6,stroke:#5e35b1,color:#311b92;
    classDef h fill:#e3f2fd,stroke:#1565c0,color:#0d47a1;
    classDef db fill:#fce4ec,stroke:#c2185b,color:#880e4f;
    classDef u fill:#fffde7,stroke:#f9a825,color:#f57f17;
    classDef x fill:#fff3e0,stroke:#ef6c00,color:#e65100;
```

---

## 3. IEC 62443-zoner & miljøer (deployment)

```mermaid
flowchart TB
    subgraph Z0["Zone 0 — Internet"]
        net(("Internet")):::z0
    end
    subgraph Z1["Zone 1 — DMZ"]
        ng["nginx<br/>rd: 80/443 · staging/prod: 8443 (DNS-01)"]:::z1
        uidist["Statisk UI-build (dist)"]:::z1
    end
    subgraph Z2["Zone 2 — Applikation"]
        fa["FastAPI / uvicorn :8000"]:::z2
        ol["Ollama :11434 · Open WebUI :8080"]:::z2
    end
    subgraph Z3["Zone 3 — Data"]
        pg[("PostgreSQL")]:::z3
        img[("Billedlager + backup")]:::z3
    end
    subgraph Z4["Zone 4 — Edge-adgang"]
        tunh["SSH-tunnel-endpoint"]:::z4
        ca["Intern CA / AccessTicket (JIT break-glass)"]:::z4
    end
    subgraph Z5["Zone 5 — Felt"]
        edge2["Edge + kamera + relæ"]:::z5
    end
    zx["Zone X — CrushFTP<br/>(ejer 21/22/80/443 på staging/prod — INGEN conduit)"]:::zx

    net -->|"conduit: TLS"| ng --> fa
    uidist --- ng
    fa --> ol
    fa --> pg
    fa --> img
    fa --> tunh --> edge2
    ca -. JIT .- tunh
    zx -. "kun portadskillelse (samme vært)" .- ng

    subgraph ENVS["Miljøer (ortogonal dimension — 3 fysiske maskiner)"]
        rd["rd — Mac Mini · timelapse.froekjaer.dk"]:::env
        stg["staging — iMac · software-parity"]:::env
        prod["prod — nyt system · timelapsepro.dk · live CrushFTP i dag"]:::env
    end
    rd -->|promote| stg -->|promote| prod

    classDef z0 fill:#ffebee,stroke:#c62828,color:#b71c1c;
    classDef z1 fill:#fff3e0,stroke:#ef6c00,color:#e65100;
    classDef z2 fill:#e3f2fd,stroke:#1565c0,color:#0d47a1;
    classDef z3 fill:#fce4ec,stroke:#c2185b,color:#880e4f;
    classDef z4 fill:#ede7f6,stroke:#5e35b1,color:#311b92;
    classDef z5 fill:#e8f5e9,stroke:#2e7d32,color:#1b5e20;
    classDef zx fill:#eceff1,stroke:#546e7a,color:#263238;
    classDef env fill:#f3e5f5,stroke:#8e24aa,color:#4a148c;
```

---

## 4. Sekvens: capture → upload → AI-tag → UI

```mermaid
sequenceDiagram
    autonumber
    participant C as Kamera
    participant E as Edge-agent
    participant H as Headend API
    participant DB as PostgreSQL
    participant O as Ollama (lokal)
    participant G as Gemini (cloud)
    participant U as Web-UI

    C->>E: Billede (gphoto2)
    E->>E: Lokal QA (NPU/CV): blur/eksp./WB
    E->>H: SFTP-upload (billede) + metadata (HTTPS, HMAC)
    H->>DB: Gem capture (camera_id, customer_id, site_id)
    H->>O: Tag-generering (lokal)
    alt Lav konfidens / kræver dyb analyse
        H->>G: Eskalér udvalgte billeder (Vertex, europe-west1)
        G-->>H: Tags / analyse
    end
    H->>DB: Gem tags + danske labels
    U->>H: Hent billeder/tags (RBAC)
    H-->>U: Billeder + danske tag-labels
```

---

## 5. Målbillede: modulær platform + udskiftelig payload

```mermaid
flowchart TB
    subgraph PLATFORM["EDGE-PLATFORM — genbrugelig, non-funktionel kerne (udvikles i ét spor)"]
        direction LR
        p1["Identitet & Enrollment<br/>(device-token, HMAC, mTLS)"]:::p
        p2["Config & Policy<br/>(hierarki, signeret pull)"]:::p
        p3["Update / OTA<br/>(signerede artifacts, rollback)"]:::p
        p4["Telemetri & Observability<br/>(SIEM · CMDB · ITIM · heartbeat)"]:::p
        p5["Remote Access<br/>(tunnel + JIT/AccessTicket + session-recording)"]:::p
        p6["HAL<br/>(orangepi/rpi/jetson/generic)"]:::p
        p7["Sikkerhed & RBAC<br/>(auth, MFA, GRC/compliance)"]:::p
        p8["Storage / Backup"]:::p
    end

    iface{{"PayloadDriver-kontrakt<br/>configure · tick · collect_telemetry · handle_command<br/>+ capability manifest · signeret payload-pakke · quota · allowlist"}}:::if

    subgraph PAYLOADS["PAYLOADS — funktionel, udskiftelig del (udvikles i parallelt spor)"]
        direction LR
        pay1["Kamera/Timelapse<br/>(Nikon/gphoto2 + billed-QA + AI-tagging)<br/>= i dag"]:::pay
        pay2["Vandværk<br/>(Modbus/OPC-UA: pumper, tryk, niveau)"]:::payf
        pay3["Vindmølle<br/>(vibration, ydelse)"]:::payf
        pay4["Solcelle<br/>(inverter-data)"]:::payf
    end

    PLATFORM --> iface
    iface --> pay1
    iface --> pay2
    iface --> pay3
    iface --> pay4

    classDef p fill:#e3f2fd,stroke:#1565c0,color:#0d47a1;
    classDef if fill:#ede7f6,stroke:#5e35b1,color:#311b92;
    classDef pay fill:#e8f5e9,stroke:#2e7d32,color:#1b5e20;
    classDef payf fill:#f1f8e9,stroke:#7cb342,color:#33691e,stroke-dasharray: 4 3;
```

*De stiplede payloads (vandværk/vind/sol) er fremtidige verticals. Pointen: alt i den blå platformkasse genbruges uændret — kun den grønne payload udskiftes.*
