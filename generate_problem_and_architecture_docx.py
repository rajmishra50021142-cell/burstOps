import os
import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import qn, nsdecls

def set_cell_background(cell, fill_hex):
    shading_elm = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{fill_hex}"/>')
    cell._tc.get_or_add_tcPr().append(shading_elm)

def set_cell_margins(cell, top=70, bottom=70, left=100, right=100):
    tcPr = cell._tc.get_or_add_tcPr()
    tcMar = OxmlElement('w:tcMar')
    for m, val in [('top', top), ('bottom', bottom), ('left', left), ('right', right)]:
        node = OxmlElement(f'w:{m}')
        node.set(qn('w:w'), str(val))
        node.set(qn('w:type'), 'dxa')
        tcMar.append(node)
    tcPr.append(tcMar)

def add_callout_box(doc, text_list, title="ARCHITECTURAL HIGHLIGHT"):
    table = doc.add_table(rows=1, cols=1)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    cell = table.cell(0, 0)
    set_cell_background(cell, "F0F4F8")
    set_cell_margins(cell, top=100, bottom=100, left=160, right=160)
    
    tcPr = cell._tc.get_or_add_tcPr()
    borders = parse_xml(f'''
        <w:tcBorders {nsdecls("w")}>
            <w:top w:val="none"/>
            <w:left w:val="single" w:sz="24" w:space="0" w:color="1B365D"/>
            <w:bottom w:val="none"/>
            <w:right w:val="none"/>
        </w:tcBorders>
    ''')
    tcPr.append(borders)
    
    p = cell.paragraphs[0]
    p.paragraph_format.space_before = Pt(2)
    p.paragraph_format.space_after = Pt(2)
    run_title = p.add_run(f"📌 {title}\n")
    run_title.font.bold = True
    run_title.font.size = Pt(9.5)
    run_title.font.color.rgb = RGBColor(0x1B, 0x36, 0x5D)
    
    for line in text_list:
        p2 = cell.add_paragraph()
        p2.paragraph_format.space_before = Pt(1)
        p2.paragraph_format.space_after = Pt(1.5)
        run = p2.add_run(line)
        run.font.size = Pt(9)
        run.font.color.rgb = RGBColor(0x33, 0x33, 0x33)

def add_code_block(doc, code_text):
    table = doc.add_table(rows=1, cols=1)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    cell = table.cell(0, 0)
    set_cell_background(cell, "F8FAFC")
    set_cell_margins(cell, top=80, bottom=80, left=120, right=120)
    
    tcPr = cell._tc.get_or_add_tcPr()
    borders = parse_xml(f'''
        <w:tcBorders {nsdecls("w")}>
            <w:top w:val="single" w:sz="4" w:space="0" w:color="CBD5E1"/>
            <w:left w:val="single" w:sz="4" w:space="0" w:color="CBD5E1"/>
            <w:bottom w:val="single" w:sz="4" w:space="0" w:color="CBD5E1"/>
            <w:right w:val="single" w:sz="4" w:space="0" w:color="CBD5E1"/>
        </w:tcBorders>
    ''')
    tcPr.append(borders)
    
    p = cell.paragraphs[0]
    p.paragraph_format.space_before = Pt(2)
    p.paragraph_format.space_after = Pt(2)
    run = p.add_run(code_text.strip())
    run.font.name = "Consolas"
    run.font.size = Pt(8.5)
    run.font.color.rgb = RGBColor(0x1E, 0x29, 0x3B)

def add_styled_image(doc, img_path, caption_text, width_inches=6.2):
    if os.path.exists(img_path):
        p_img = doc.add_paragraph()
        p_img.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_img.paragraph_format.space_before = Pt(8)
        p_img.paragraph_format.space_after = Pt(2)
        run = p_img.add_run()
        run.add_picture(img_path, width=Inches(width_inches))
        
        p_cap = doc.add_paragraph()
        p_cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_cap.paragraph_format.space_before = Pt(0)
        p_cap.paragraph_format.space_after = Pt(8)
        run_cap = p_cap.add_run(f"Figure: {caption_text}")
        run_cap.font.italic = True
        run_cap.font.size = Pt(8.5)
        run_cap.font.color.rgb = RGBColor(0x4B, 0x55, 0x63)
    else:
        p = doc.add_paragraph(f"[Image Missing: {img_path}]")
        p.runs[0].font.color.rgb = RGBColor(0xC0, 0x00, 0x00)

def build_docx():
    doc = docx.Document()
    
    for sec in doc.sections:
        sec.top_margin = Inches(0.75)
        sec.bottom_margin = Inches(0.75)
        sec.left_margin = Inches(0.75)
        sec.right_margin = Inches(0.75)
        
        # Setup Running Header & Footer
        header = sec.header
        p_hdr = header.paragraphs[0]
        p_hdr.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        r_hdr = p_hdr.add_run("BurstOps: Layer-7 Elastic Burst Gateway | Master Architecture Spec")
        r_hdr.font.name = "Calibri"
        r_hdr.font.size = Pt(8)
        r_hdr.font.color.rgb = RGBColor(0x94, 0xA3, 0xB8)
        
        footer = sec.footer
        p_ftr = footer.paragraphs[0]
        p_ftr.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r_ftr = p_ftr.add_run("BurstOps Engineering Documentation — Microsoft Azure Architecture")
        r_ftr.font.name = "Calibri"
        r_ftr.font.size = Pt(8)
        r_ftr.font.color.rgb = RGBColor(0x94, 0xA3, 0xB8)
        
    normal_style = doc.styles['Normal']
    normal_style.font.name = 'Calibri'
    normal_style.font.size = Pt(10)
    normal_style.font.color.rgb = RGBColor(0x22, 0x22, 0x22)
    
    # Document Header Title
    p_title = doc.add_paragraph()
    p_title.paragraph_format.space_before = Pt(0)
    p_title.paragraph_format.space_after = Pt(2)
    run_t = p_title.add_run("BurstOps: Problem Statement, Architectural Specification & Future Roadmap")
    run_t.font.bold = True
    run_t.font.size = Pt(20)
    run_t.font.color.rgb = RGBColor(0x1B, 0x36, 0x5D)
    
    p_sub = doc.add_paragraph()
    p_sub.paragraph_format.space_before = Pt(0)
    p_sub.paragraph_format.space_after = Pt(10)
    run_sub = p_sub.add_run("Comprehensive Engineering Spec: The HPA Lag Problem, Hybrid Architectural Justification, Complete Tech Stack, and 100% Cloud Enterprise Roadmap")
    run_sub.font.italic = True
    run_sub.font.size = Pt(11)
    run_sub.font.color.rgb = RGBColor(0x47, 0x55, 0x69)
    
    # Metadata Table
    meta_table = doc.add_table(rows=3, cols=2)
    meta_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    meta_data = [
        [("Project Name", "BurstOps (Layer-7 Elastic Burst Gateway)"), ("Document Status", "Master Architecture Specification")],
        [("Current Implementation", "Option A Hybrid (Local K8s Stand-in + Live Azure Serverless Target)"), ("Target Cloud Platform", "Microsoft Azure (centralindia)")],
        [("Active Azure Subscription", "Azure for Students (c6e32bdf-69dd-4451-8c44-7b35c5ad187b, Enabled)"), ("Target Production Roadmap", "100% Cloud Enterprise Deployment (AKS + ACR + Functions + Private Endpoints)")]
    ]
    for row_idx, row in enumerate(meta_table.rows):
        for col_idx, cell in enumerate(row.cells):
            set_cell_background(cell, "F8FAFC")
            set_cell_margins(cell, top=45, bottom=45, left=80, right=80)
            title, val = meta_data[row_idx][col_idx]
            p = cell.paragraphs[0]
            p.paragraph_format.space_before = Pt(1)
            p.paragraph_format.space_after = Pt(1)
            r1 = p.add_run(f"{title}: ")
            r1.font.bold = True
            r1.font.size = Pt(8.5)
            r2 = p.add_run(val)
            r2.font.size = Pt(8.5)
            
    doc.add_paragraph().paragraph_format.space_after = Pt(6)

    # Executive Summary
    h_exec = doc.add_heading("Executive Summary", level=2)
    h_exec.runs[0].font.color.rgb = RGBColor(0x1B, 0x36, 0x5D)
    doc.add_paragraph(
        "BurstOps is an asynchronous, Layer-7 intelligent reverse proxy and traffic deflection gateway engineered to eliminate the "
        "Kubernetes Horizontal Pod Autoscaler (HPA) Provisioning Lag. In modern cloud-native architectures, sudden, unpredictable traffic "
        "spikes cause container CPU utilization to instantly saturate. Although Kubernetes HPA is configured to autoscale pods, there is a "
        "fundamental, unavoidable delay of 60 to 90+ seconds between the onset of a spike and the moment newly scheduled pods pass readiness probes "
        "and register with the Service endpoints. During this window—the 'Meltdown Window'—existing pods experience CPU starvation, socket buffer "
        "exhaustion, request queue overflow, and cascading HTTP 504 Gateway Timeouts.\n\n"
        "BurstOps acts as an operational shock absorber that does NOT replace HPA, but rather buys HPA the time it needs to scale. "
        "The instant cluster CPU crosses an operational threshold (80%), BurstOps dynamically deflects excess baseline traffic to public cloud serverless "
        "compute (Azure Functions on Flex Consumption) using sub-millisecond Proportional-Integral (PI) control and cryptographic HMAC-SHA256 authentication. "
        "Once HPA brings new pods online and cluster CPU recovers below 60%, BurstOps smoothly reduces deflection back to zero, returning 100% of traffic "
        "to on-cluster resources."
    )

    # 1. Detailed Problem Statement
    h1 = doc.add_heading("1. Detailed Problem Statement & Real-World Failure Modes", level=1)
    h1.runs[0].font.color.rgb = RGBColor(0x1B, 0x36, 0x5D)
    
    h2 = doc.add_heading("1.1 The Anatomy of the 60 to 90+ Second HPA Provisioning Lag", level=2)
    h2.runs[0].font.color.rgb = RGBColor(0x2C, 0x52, 0x82)
    
    doc.add_paragraph(
        "In modern containerized microservice architectures, Kubernetes Horizontal Pod Autoscaler (HPA) is the de-facto industry standard "
        "for dynamically scaling application workloads based on CPU and memory utilization. However, despite its widespread adoption, "
        "HPA suffers from a fundamental, unavoidable architectural bottleneck: Provisioning Lag."
    )
    
    doc.add_paragraph(
        "When an unexpected, abrupt traffic spike occurs (e.g. flash sales, viral social surges, black friday checkout spikes, or batch job bursts), "
        "Kubernetes cannot react instantaneously. The autoscaling pipeline introduces compounding delays across multiple discrete stages:\n\n"
        "1. Metrics Scraping Window (15–30 seconds): Scrapers (such as Metrics Server, Prometheus, or cAdvisor) do not react to instantaneous CPU spikes; "
        "they sample container cgroups periodically and calculate sliding-window rates (e.g. rate(container_cpu_usage_seconds_total[30s])) to prevent thrashing.\n\n"
        "2. HPA Evaluation Loop (15 seconds): By default, the Kubernetes kube-controller-manager evaluates HPA scaling algorithms every 15 seconds.\n\n"
        "3. Scheduling Latency (5–10 seconds): The Kubernetes API server and kube-scheduler must identify available nodes with sufficient CPU/memory requests, "
        "bind the pod to a worker node, and update cluster etcd state.\n\n"
        "4. Image Pulling & Unpacking (10–30+ seconds): Even when images are cached, container runtime engines (containerd / CRI-O) must unpack layer tarballs, "
        "allocate overlay filesystems, and attach network namespaces.\n\n"
        "5. Language Runtime Bootstrap & Readiness Probes (15–30 seconds): High-level application frameworks (Python ASGI, Java Spring Boot, Node.js) "
        "take several seconds to import libraries, compile bytecode, establish database connection pools, and pass readinessProbe HTTP health checks before "
        "the Kube-Proxy endpoints controller registers the pod into the Service VIP."
    )
    
    h2 = doc.add_heading("1.2 The Production Consequence: The 'Meltdown Window'", level=2)
    h2.runs[0].font.color.rgb = RGBColor(0x2C, 0x52, 0x82)
    
    doc.add_paragraph(
        "During these 60 to 90+ seconds, existing pods bear the full brunt of the traffic surge. This triggers a cascading collapse:\n"
        "• CPU Starvation: Worker threads spend 100% of their cycles in context switching or CPU-bound loops, starving asynchronous event loops.\n"
        "• TCP Socket Buffer Exhaustion: The Linux socket listen backlog (somaxconn) and TCP accept queue fill completely; ingress proxies fail to establish TCP handshakes.\n"
        "• Cascading HTTP Timeouts: Upstream reverse proxies (Nginx Ingress, AWS ALB, Azure App Gateway, Cloudflare) exceed timeout thresholds, returning HTTP 504 Gateway Timeout and HTTP 502 Bad Gateway to end users.\n"
        "• Liveness Probe Death Spiral: Overloaded pods fail to respond to Kubernetes /healthz liveness probes. Kubelet interprets this as an application deadlock, forcibly killing pods with SIGKILL. The resulting CrashLoopBackOff cycle reduces cluster capacity further, ensuring total system collapse."
    )
    
    h2 = doc.add_heading("1.3 Why Naive Alternatives Fail in Production", level=2)
    h2.runs[0].font.color.rgb = RGBColor(0x2C, 0x52, 0x82)
    
    doc.add_paragraph(
        "• Lowering HPA CPU Target (e.g. from 80% to 40%): Leads to permanent cluster over-provisioning, wasting thousands of dollars in idle cloud compute during off-peak hours, yet still fails when a sudden 10x surge arrives faster than the 90-second spin-up time.\n"
        "• Pre-Provisioning Massive VM Reserve Pools: Economically unviable and antithetical to cloud-native elasticity. Idle VMs in Virtual Machine Scale Sets accrue full hourly charges, OS disk fees, and load balancer costs.\n"
        "• Aggressive 24/7 Pod Over-Provisioning: Running 10-20 idle pod replicas permanently is a FinOps disaster for any cost-conscious engineering organization."
    )
    
    add_callout_box(doc, [
        "• The BurstOps Thesis: BurstOps does NOT replace HPA; it acts as an operational shock absorber that BUYS HPA TIME.",
        "• Core Objective: The instant CPU crosses 80%, deflect overflow traffic to serverless functions in milliseconds.",
        "• Outcome: Zero dropped requests, sub-second p95 response times, and zero pod crashes while HPA brings new pods online."
    ], title="CORE PROBLEM STATEMENT & SOLUTION")

    # 2. System Architecture & Diagram
    h1 = doc.add_heading("2. Complete System Architecture & Interaction Model", level=1)
    h1.runs[0].font.color.rgb = RGBColor(0x1B, 0x36, 0x5D)
    
    doc.add_paragraph(
        "Below is the complete architectural topology and interaction blueprint of the BurstOps system, detailing the relationships "
        "between clients, gateway control logic, telemetry pipelines, cloud integration, operations, and compute backends:"
    )
    
    # EMBED THE MASTER ARCHITECTURE DIAGRAM
    add_styled_image(doc, "docs/architecture/system_architecture_diagram.png",
                     "BurstOps Master Architecture Diagram: Gateway Control, Telemetry State, Cloud Integration, Operations & Request Compute", width_inches=6.2)
    
    h2 = doc.add_heading("2.1 Subsystem Breakdown & Component Interactions", level=2)
    h2.runs[0].font.color.rgb = RGBColor(0x2C, 0x52, 0x82)
    
    doc.add_paragraph(
        "The architecture is organized into five tightly coupled, highly cohesive subsystems:\n\n"
        "1. Gateway Control Subsystem (gateway.py):\n"
        "   • Gateway API: Asynchronous Layer-7 reverse proxy built with FastAPI and Uvicorn. Handles incoming /calculate requests and distributes traffic.\n"
        "   • CPU Poller: Dedicated background daemon polling Prometheus metrics every 2.0 seconds.\n"
        "   • Routing State Engine: Evaluates the hysteresis finite state machine (80% Burst / 60% Recovery) to prevent route flapping.\n"
        "   • PI Controller: Continuous Proportional-Integral controller computing dynamic deflection ratio r(t) with anti-windup clamping [0.0, 1.0].\n"
        "   • HMAC Signer: Cryptographic signer generating HMAC-SHA256 digests over timestamps and request bodies for cloud requests.\n\n"
        "2. Telemetry State Subsystem:\n"
        "   • Prometheus (prometheus.yml): Time-series metrics engine scraping cAdvisor, cpu-sim, and gateway metrics on a 2s cadence.\n"
        "   • CPU Simulator (app.py): PromQL-compatible synthetic metrics generator allowing deterministic testing with inertia glide curves.\n"
        "   • Redis Backplane (redis_backplane.py): High-performance distributed coordination store for multi-replica leader lease and pub/sub state broadcasting.\n\n"
        "3. Cloud Integration Subsystem:\n"
        "   • Azure Function (function_app.py): Production serverless burst target running on Azure Flex Consumption (Python 3.13 in Central India).\n"
        "   • Local Function (dummy-serverless/app.py): Offline local serverless stand-in with 50-150ms artificial latency injection for local testing.\n"
        "   • HMAC Verifier (hmac_util.py): Timing-safe verifier checking x-functions-key, x-gateway-timestamp, and x-gateway-signature.\n\n"
        "4. Operations Subsystem:\n"
        "   • Grafana Dashboard (burstops.json): Real-time 12-panel dashboard tracking routing mode, CPU curve, deflection ratio, and FinOps metrics.\n"
        "   • Cost Model (costing.py): Evaluates cloud unit economics, serverless invocation premiums, and the 28.55 RPS breakeven boundary.\n"
        "   • Tracing Hooks (tracing.py): Injects W3C traceparent distributed context with adaptive sampling (100% burst / 5% baseline).\n"
        "   • Trace Collector: OTLP collector ingesting distributed spans.\n\n"
        "5. Request Compute Subsystem:\n"
        "   • Backend VIP (nginx.conf): Nginx reverse proxy simulating a Kubernetes ClusterIP Service, balancing round-robin between worker pods.\n"
        "   • Kubernetes Backend (dummy-backend/app.py): Pod replicas executing the deterministic Sieve of Eratosthenes prime calculation canary."
    )

    # 3. Technologies Used & Why
    h1 = doc.add_heading("3. Technologies Used & Architectural Justifications", level=1)
    h1.runs[0].font.color.rgb = RGBColor(0x1B, 0x36, 0x5D)
    
    doc.add_paragraph(
        "Every single library, engine, and cloud component in BurstOps was selected after evaluating production trade-offs. "
        "The table below outlines what we used and why:"
    )
    
    tech_table = doc.add_table(rows=1, cols=3)
    tech_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    thdr = tech_table.rows[0].cells
    thdr[0].text = "Technology / Tool"
    thdr[1].text = "Role in Project"
    thdr[2].text = "Why We Used It (Architectural Justification)"
    for c in thdr:
        set_cell_background(c, "1B365D")
        c.paragraphs[0].runs[0].font.bold = True
        c.paragraphs[0].runs[0].font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
        set_cell_margins(c, top=60, bottom=60, left=80, right=80)
        
    tech_rows = [
        ("FastAPI & Uvicorn", "Layer-7 Gateway Router", "Asynchronous ASGI execution gives high throughput and sub-millisecond routing overhead with <50MB RAM footprint."),
        ("Nginx (1.27-Alpine)", "Backend VIP / Load Balancer", "Industry standard for high-performance TCP/HTTP reverse proxying; faithfully simulates Kubernetes ClusterIP Service round-robin balancing."),
        ("Prometheus (v2.53)", "Metrics Engine & Scraper", "Pull-based metrics collection with standard PromQL query evaluation; accurately models real-world 30-second sliding rate windows."),
        ("Redis 7 (Alpine)", "Distributed State & Lock", "Sub-millisecond memory performance; native Lua scripting engine enables atomic Compare-And-Set (CAS) leader election without external dependencies."),
        ("Grafana (v11.1.4)", "Observability Dashboard", "Real-time visual monitoring with declarative JSON provisioning; allows live visualization of routing mode, CPU curve, deflection ratio, and FinOps gauges."),
        ("Azure Functions (Flex Consumption)", "Cloud Serverless Burst Target", "Sub-second container cold-starts, instantaneous auto-concurrency, zero idle compute costs, and 1,000,000 free monthly executions under Azure for Students."),
        ("Azure Application Insights", "Distributed Cloud Telemetry", "Deep serverless telemetry; provides automatic Application Map topology, latency percentile distribution, and real-time QuickPulse streaming with strict 0.15 GB/day budget caps."),
        ("Terraform (IaC)", "Cloud Infrastructure as Code", "Declarative, repeatable cloud infrastructure provisioning; automates secret generation (HMAC keys) and provisions resource groups, storage, and budgets without manual portal drift."),
        ("HMAC-SHA256 Cryptography", "Inter-Cloud Security Protocol", "Timing-safe cryptographic signature over timestamp and body; rejects tampered payloads and replays (>300s) without the complexity and latency of mTLS."),
        ("Pytest & Coverage", "Invariant Testing Suite", "Automated formal verification; 89 test cases guarantee mathematical correctness across hysteresis state transitions, HMAC security, and PI control.")
    ]
    for idx, (tech, role, why) in enumerate(tech_rows):
        row = tech_table.add_row().cells
        row[0].text = tech
        row[1].text = role
        row[2].text = why
        for c in row:
            set_cell_background(c, "F9FAFB" if idx % 2 == 0 else "FFFFFF")
            set_cell_margins(c, top=45, bottom=45, left=60, right=60)
            c.paragraphs[0].runs[0].font.size = Pt(8.5)

    doc.add_paragraph().paragraph_format.space_after = Pt(6)

    # 4. Project Workflow & End-to-End Operational Lifecycle
    h1 = doc.add_heading("4. Comprehensive Project Workflow & Operational Data Lifecycle", level=1)
    h1.runs[0].font.color.rgb = RGBColor(0x1B, 0x36, 0x5D)
    
    doc.add_paragraph(
        "BurstOps operates as an autonomous, closed-loop cybernetic feedback system. Rather than viewing the architecture "
        "as a static set of components, its real-world implementation is best understood through its five-stage continuous operational workflow:"
    )
    
    h2 = doc.add_heading("4.1 Stage 1: Ingestion, Traffic Classification & Steady-State Routing", level=2)
    h2.runs[0].font.color.rgb = RGBColor(0x2C, 0x52, 0x82)
    doc.add_paragraph(
        "• Client Request Ingestion: Incoming Layer-7 HTTP requests (e.g. /calculate) from end-user clients arrive at the asynchronous BurstOps reverse proxy gateway (FastAPI running on ASGI Uvicorn).\n"
        "• Baseline Operational Regime: In normal operating conditions, cluster CPU utilization remains well below the operational threshold (CPU < 80%). The routing state machine maintains BASELINE MODE with a deflection ratio r(t) = 0.0.\n"
        "• Round-Robin Cluster Dispatch: 100% of client traffic is routed internally to the on-cluster Virtual IP (Nginx reverse proxy simulating a Kubernetes ClusterIP Service), balancing traffic evenly across worker pod replicas.\n"
        "• Compute Canary Execution: Worker pods execute a standardized CPU-intensive benchmark: Sieve of Eratosthenes over [2..1000] (generating 168 primes, sum 76,127), establishing deterministic compute baselines with sub-millisecond local network latency."
    )
    
    h2 = doc.add_heading("4.2 Stage 2: High-Frequency Telemetry Sampling & Inertia-Aware Sensing", level=2)
    h2.runs[0].font.color.rgb = RGBColor(0x2C, 0x52, 0x82)
    doc.add_paragraph(
        "• Continuous Telemetry Polling: The gateway control plane executes an asynchronous background daemon that queries Prometheus metrics on an aggressive 2.0-second scrape interval.\n"
        "• Sliding-Window Rate Evaluation: Telemetry queries evaluate PromQL expressions: rate(container_cpu_usage_seconds_total[30s]). This 30-second moving window matches production container cgroup scrapers (cAdvisor / Kubernetes Metrics Server), filtering out instantaneous sub-second noise while reliably capturing sustained surges.\n"
        "• Inertia Simulation Engine: For controlled local benchmarking, a synthetic CPU simulator models realistic hardware thermal and processing inertia curves, allowing repeatable verification of ramp-up, peak saturation, and cooling phases without host OS variance."
    )
    
    h2 = doc.add_heading("4.3 Stage 3: Distributed Closed-Loop Decision Engine & Consensus", level=2)
    h2.runs[0].font.color.rgb = RGBColor(0x2C, 0x52, 0x82)
    doc.add_paragraph(
        "• Distributed Coordination via Redis Backplane: To support horizontally scaled multi-replica gateway deployments without creating a thundering herd on Prometheus, gateways coordinate via Redis 7.\n"
        "• Atomic Leader Election: Gateway replicas use an atomic Lua Compare-And-Set (CAS) script with a short-lived distributed lease key (burstops:leader:lock). Exactly one replica acts as the telemetry leader, polling Prometheus and running the control loop.\n"
        "• Asymmetric Hysteresis State Machine: To prevent rapid oscillating between routing modes ('route flapping') near threshold boundaries:\n"
        "   - Switches to BURST MODE when CPU >= 80%.\n"
        "   - Transitions to RECOVERY MODE only when CPU drops below 60%.\n"
        "   - The 20% hysteresis gap ensures mathematical stability.\n"
        "• Continuous Proportional-Integral (PI) Deflection Math: Rather than a crude all-or-nothing binary failover, the control engine dynamically calculates a continuous deflection ratio:\n"
        "   r(t) = clamp(Kp * e(t) + Ki * ∫e(t)dt, 0.0, 1.0)\n"
        "   where e(t) = CPU(t) - 75% relative to the target setpoint. Anti-windup clamping prevents integral saturation, and a slew-rate limiter (<= 0.10/s) prevents sudden traffic shock.\n"
        "• Zero-Latency In-Memory Synchronization: The leader broadcasts r(t) and routing mode across a Redis Pub/Sub channel. Worker gateway replicas update a local in-memory cache, enabling sub-millisecond (<0.05ms) routing decisions with zero Redis I/O on the critical request path."
    )
    
    h2 = doc.add_heading("4.4 Stage 4: Cryptographic Inter-Cloud Deflection & Elastic Serverless Execution", level=2)
    h2.runs[0].font.color.rgb = RGBColor(0x2C, 0x52, 0x82)
    doc.add_paragraph(
        "• Dynamic Traffic Splitting: When r(t) > 0.0, incoming traffic is split proportionally: fraction (1 - r(t)) continues to the local Kubernetes cluster, while overflow fraction r(t) is deflected externally to serverless compute.\n"
        "• HMAC-SHA256 Wire Cryptography (Zero-Trust): To secure traffic over the public internet between gateway and cloud without the operational complexity and handshake latency of mutual TLS (mTLS), every deflected request is signed with an HMAC-SHA256 digest over the timestamp and payload body.\n"
        "• Timing-Safe Cloud Verification: The cloud burst target (Azure Functions on Flex Consumption running Python 3.13 in Central India) verifies the signature using constant-time comparison (hmac.compare_digest) and rejects requests older than 300 seconds to prevent replay attacks.\n"
        "• Instant Elastic Scale-Out: Serverless compute instances scale out in milliseconds from 0 to hundreds of concurrent executions with zero cold idle cost ($0.00 when idle, with 1,000,000 free monthly executions under student plans)."
    )
    
    h2 = doc.add_heading("4.5 Stage 5: Autonomous Surge Absorption, HPA Convergence & Graceful Recovery", level=2)
    h2.runs[0].font.color.rgb = RGBColor(0x2C, 0x52, 0x82)
    doc.add_paragraph(
        "• Absorbing the 90-Second Meltdown Window: While BurstOps absorbs the immediate surge in milliseconds, Kubernetes HPA completes its multi-stage spin-up cycle (metric scraping, controller evaluation, scheduling, image pulling, and readiness probes).\n"
        "• Cluster Capacity Multiplication: Once newly scheduled Kubernetes pods pass readiness probes and join the Service endpoints, aggregate cluster compute capacity expands, causing local CPU utilization to naturally plunge from 95%+ down into the safe 40-55% range.\n"
        "• Graceful Recovery Back to Baseline: Sensing CPU drop below the 60% recovery threshold, the PI controller smoothly dials r(t) back to 0.0, seamlessly returning 100% of traffic back to the on-cluster pods without dropping a single connection.\n"
        "• Distributed Observability & FinOps Reconciliation: Throughout the entire lifecycle, OpenTelemetry W3C traceparent headers propagate distributed context across cluster and serverless boundaries (adaptive sampling: 100% during burst, 5% during baseline). Real-time telemetry is streamed to Azure Application Insights and Grafana, while the FinOps costing engine reconciles the burst premium against the 28.55 RPS breakeven boundary."
    )

    # 5. Why We Did NOT Use AKS / ACR (Decision Log)
    h1 = doc.add_heading("5. Architectural Decision Log: Why We Did NOT Deploy AKS on Azure", level=1)
    h1.runs[0].font.color.rgb = RGBColor(0x1B, 0x36, 0x5D)
    
    doc.add_paragraph(
        "A critical engineering decision in this project was choosing Option A (Hybrid Architecture: Local Kubernetes Mesh + Live Azure Serverless Target) "
        "instead of deploying a full Azure Kubernetes Service (AKS) cluster and Azure Container Registry (ACR) on Azure. Below is the transparent architectural rationale:"
    )
    
    h2 = doc.add_heading("5.1 The Financial Reality of Azure for Students Subscriptions", level=2)
    h2.runs[0].font.color.rgb = RGBColor(0x2C, 0x52, 0x82)
    doc.add_paragraph(
        "Azure for Students provides a fixed $100 one-time annual credit with strict non-renewable quota boundaries. Unlike enterprise corporate "
        "subscriptions with monthly billing accounts, student subscriptions possess zero financial buffer. Once credit is exhausted, Microsoft's automated "
        "billing guardrails immediately disable the subscription."
    )
    
    h2 = doc.add_heading("5.2 The Continuous Cost Drain of Running an AKS Cluster", level=2)
    h2.runs[0].font.color.rgb = RGBColor(0x2C, 0x52, 0x82)
    doc.add_paragraph(
        "An active AKS cluster requires a Virtual Machine Scale Set (VMSS) agent node pool. Even with the smallest practical VM SKU (Standard_B2s with 2 vCPUs and 4 GiB RAM), "
        "the VMSS compute, managed OS disk storage, Public IP addresses, and Azure Load Balancer run 24 hours a day, 7 days a week.\n"
        "• VM Compute (Standard_B2s): ~$26.28/month\n"
        "• Managed OS SSD Disk (32 GB): ~$4.80/month\n"
        "• Standard Load Balancer & Public IP: ~$21.90/month\n"
        "• Total Fixed Cost: ~$52.98 per month — even when completely idle and serving zero traffic!\n\n"
        "An active AKS cluster running continuously would exhaust the entire $100 credit pool in less than 60 days."
    )
    
    h2 = doc.add_heading("5.3 Root Cause Analysis (RCA) of the Prior Outage", level=2)
    h2.runs[0].font.color.rgb = RGBColor(0x2C, 0x52, 0x82)
    doc.add_paragraph(
        "In the previous iteration of this project, a full AKS cluster (burstops-aks) and container registry (burstopsacr) were deployed on Azure. "
        "Within weeks, the idle VMSS nodes drained the entire $100 credit balance. Microsoft's automated billing guardrails immediately set the subscription state "
        "to 'Disabled', shutting down compute and returning 'HTTP 403 Site Disabled' on all endpoints. This empirical proof confirmed that running an idle "
        "Kubernetes cluster on a capped student subscription is an operational anti-pattern."
    )
    
    h2 = doc.add_heading("5.4 The Technical & Operational Superiority of Option A (Hybrid Architecture)", level=2)
    h2.runs[0].font.color.rgb = RGBColor(0x2C, 0x52, 0x82)
    doc.add_paragraph(
        "• Local Kubernetes Mesh (Docker Compose): Replicates 100% of Kubernetes pod networking, Nginx ClusterIP VIP round-robin balancing, and cAdvisor metric scraping at $0.00 cost.\n"
        "• Live Azure Serverless Target (Flex Consumption): Real public cloud execution, real internet boundary traversal, real HMAC cryptographic authentication, and real Azure Application Insights telemetry. "
        "Because Flex Consumption charges strictly per millisecond of execution ($0.00 when idle, with 1,000,000 free monthly executions), it provides 100% of the verification proof with zero credit drain."
    )
    
    add_callout_box(doc, [
        "• Strategic Decision: Option A delivered 100% of the educational and verification value without burning the student subscription.",
        "• Zero Compromise: Real HMAC signing, real internet hops to Central India, and real Azure Portal telemetry were all proven live."
    ], title="COST DISCIPLINE & ARCHITECTURAL PRUDENCE")

    # 6. Future Implementation Roadmap (100% Cloud)
    h1 = doc.add_heading("6. Future Implementation Roadmap: 100% Cloud Architecture & Verification", level=1)
    h1.runs[0].font.color.rgb = RGBColor(0x1B, 0x36, 0x5D)
    
    doc.add_paragraph(
        "When transitioning from academic evaluation to a production enterprise deployment with a corporate Pay-As-You-Go subscription, "
        "BurstOps can be seamlessly migrated to a 100% Azure Cloud Architecture. Below is the engineering implementation blueprint:"
    )
    
    h2 = doc.add_heading("6.1 Phase 1: Cloud Infrastructure Provisioning with Terraform", level=2)
    h2.runs[0].font.color.rgb = RGBColor(0x2C, 0x52, 0x82)
    doc.add_paragraph(
        "• Azure Kubernetes Service (AKS): Provision azurerm_kubernetes_cluster with a System node pool (1x Standard_B2s for CoreDNS/Ingress) "
        "and a User node pool with auto-scaling enabled (min: 2, max: 10 nodes).\n"
        "• Azure Container Registry (ACR): Provision azurerm_container_registry (Standard SKU) with system-assigned managed identity role assignment (AcrPull) to AKS.\n"
        "• Virtual Network (VNet) Topology: Create an Azure Virtual Network with three dedicated subnets:\n"
        "   1. AKS Node Subnet (10.0.1.0/24)\n"
        "   2. Application Gateway / Ingress Subnet (10.0.2.0/24)\n"
        "   3. Serverless Private Endpoint Subnet (10.0.3.0/24)"
    )
    
    h2 = doc.add_heading("6.2 Phase 2: Container Packaging & CI/CD Pipeline", level=2)
    h2.runs[0].font.color.rgb = RGBColor(0x2C, 0x52, 0x82)
    doc.add_paragraph(
        "• Automated GitHub Actions workflow building and pushing three production container images to ACR:\n"
        "   - burstopsacr.azurecr.io/gateway:latest\n"
        "   - burstopsacr.azurecr.io/dummy-backend:latest\n"
        "   - burstopsacr.azurecr.io/prometheus:latest"
    )
    
    h2 = doc.add_heading("6.3 Phase 3: Kubernetes Manifest Deployment (k8s/)", level=2)
    h2.runs[0].font.color.rgb = RGBColor(0x2C, 0x52, 0x82)
    doc.add_paragraph(
        "• Deploy the manifests already authored in the repository:\n"
        "   - gateway-deployment.yaml: Deploying 3 gateway replicas with anti-affinity across AKS nodes.\n"
        "   - gateway-service.yaml: ClusterIP service exposing the gateway.\n"
        "   - ingress.yaml: Configuring Azure Application Gateway (AGIC) or Nginx Ingress Controller with SSL/TLS termination.\n"
        "   - hpa.yaml: Configuring the Horizontal Pod Autoscaler for the backend pods (minReplicas: 2, maxReplicas: 10, targetCPU: 70%)."
    )
    
    add_code_block(doc, """apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: backend-hpa
  namespace: burstops
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: backend-service
  minReplicas: 2
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70""")
    
    h2 = doc.add_heading("6.4 Phase 4: Enterprise Zero-Trust Private Networking", level=2)
    h2.runs[0].font.color.rgb = RGBColor(0x2C, 0x52, 0x82)
    doc.add_paragraph(
        "• Establish an Azure Private Endpoint between the AKS cluster subnet and the Azure Function (func-burstops-live).\n"
        "• Eliminates public internet traversal; all burst deflection flows privately across the Microsoft Azure backbone over private IP addresses (10.0.3.5) with zero exposure to public DNS."
    )
    
    h2 = doc.add_heading("6.5 Phase 5: 100% Cloud Verification & Load Test Runbook", level=2)
    h2.runs[0].font.color.rgb = RGBColor(0x2C, 0x52, 0x82)
    doc.add_paragraph(
        "• Load Generation: Deploy distributed Locust workers via Azure Container Instances (ACI) generating 1,000+ concurrent RPS against the public Ingress IP.\n"
        "• Verification Metric 1 (HPA Scale-Out): Execute 'kubectl get hpa -w' to observe the 90-second pod scale-out window (pods scaling from 2 to 10).\n"
        "• Verification Metric 2 (Burst Deflection Correlation): In Azure Application Insights, correlate the exact 90-second HPA lag window with serverless invocation spikes.\n"
        "• Verification Metric 3 (Surge Absorption & Stabilization): As new AKS pods reach Ready status, observe the BurstOps gateway automatically reducing the deflection ratio r(t) back to 0.0%.\n"
        "• Verification Metric 4 (Cloud FinOps Reconciliation): In Azure Cost Management, reconcile the total cost of serverless invocations versus AKS compute hours to validate the 28.55 RPS breakeven formula in production."
    )
    
    add_callout_box(doc, [
        "• Ready for Enterprise Cloud: All Kubernetes manifests (k8s/) and Terraform definitions already exist in the codebase.",
        "• Direct Transition Path: Migrating to 100% cloud requires only running 'terraform apply' on a funded subscription."
    ], title="FUTURE CLOUD READINESS")

    out_file = "/Users/rajmishara/burstOps/BURSTOPS_PROBLEM_STATEMENT_AND_ARCHITECTURE_SPEC.docx"
    doc.save(out_file)
    print(f"Spec DOCX successfully built at {out_file} (Size: {os.path.getsize(out_file):,} bytes)")

if __name__ == "__main__":
    build_docx()
