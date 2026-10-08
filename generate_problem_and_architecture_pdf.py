import os
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle, PageBreak, KeepTogether
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfgen import canvas

class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super(NumberedCanvas, self).__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super(NumberedCanvas, self).showPage()
        super(NumberedCanvas, self).save()

    def draw_page_decorations(self, page_count):
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#64748B"))
        
        # Running Header (pages > 1)
        if self._pageNumber > 1:
            self.drawString(54, 11 * inch - 36, "BurstOps: Problem Statement, Architectural Specification & Future Roadmap")
            self.setStrokeColor(colors.HexColor("#CBD5E1"))
            self.setLineWidth(0.5)
            self.line(54, 11 * inch - 42, 8.5 * inch - 54, 11 * inch - 42)
            
        # Running Footer
        page_str = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(8.5 * inch - 54, 36, page_str)
        self.drawString(54, 36, "BurstOps Engineering Documentation — Microsoft Azure Architecture")
        self.setStrokeColor(colors.HexColor("#CBD5E1"))
        self.setLineWidth(0.5)
        self.line(54, 46, 8.5 * inch - 54, 46)
        
        self.restoreState()

def build_pdf():
    pdf_path = "/Users/rajmishara/burstOps/BURSTOPS_PROBLEM_STATEMENT_AND_ARCHITECTURE_SPEC.pdf"
    doc = SimpleDocTemplate(
        pdf_path,
        pagesize=letter,
        leftMargin=54,
        rightMargin=54,
        topMargin=50,
        bottomMargin=50
    )
    
    styles = getSampleStyleSheet()
    
    # Custom Palette
    c_primary = colors.HexColor("#1B365D")
    c_secondary = colors.HexColor("#2C5282")
    c_text = colors.HexColor("#1E293B")
    c_bg_light = colors.HexColor("#F8FAFC")
    c_accent = colors.HexColor("#0D9488")
    
    # Custom Typography Styles
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=18,
        leading=22,
        textColor=c_primary,
        spaceAfter=2
    )
    
    sub_style = ParagraphStyle(
        'DocSub',
        parent=styles['Normal'],
        fontName='Helvetica-Oblique',
        fontSize=9.5,
        leading=13,
        textColor=colors.HexColor("#475569"),
        spaceAfter=8
    )
    
    h1_style = ParagraphStyle(
        'DocH1',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=12,
        leading=15,
        textColor=c_primary,
        spaceBefore=10,
        spaceAfter=4,
        keepWithNext=True
    )
    
    h2_style = ParagraphStyle(
        'DocH2',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10,
        leading=13,
        textColor=c_secondary,
        spaceBefore=6,
        spaceAfter=3,
        keepWithNext=True
    )
    
    body_style = ParagraphStyle(
        'DocBody',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=11.5,
        textColor=c_text,
        spaceAfter=4
    )
    
    caption_style = ParagraphStyle(
        'DocCaption',
        parent=styles['Normal'],
        fontName='Helvetica-Oblique',
        fontSize=7.5,
        leading=10,
        textColor=colors.HexColor("#64748B"),
        alignment=1,
        spaceBefore=3,
        spaceAfter=6
    )
    
    code_style = ParagraphStyle(
        'DocCode',
        parent=styles['Normal'],
        fontName='Courier',
        fontSize=7,
        leading=9.5,
        textColor=colors.HexColor("#0F172A")
    )
    
    callout_title_style = ParagraphStyle(
        'CalloutTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8,
        leading=10.5,
        textColor=c_primary,
        spaceAfter=2
    )
    
    callout_body_style = ParagraphStyle(
        'CalloutBody',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=7.5,
        leading=10.5,
        textColor=c_text,
        spaceAfter=1
    )

    story = []
    
    # Title & Subtitle
    story.append(Paragraph("BurstOps: Problem Statement, Architectural Specification & Future Roadmap", title_style))
    story.append(Paragraph("Comprehensive Engineering Spec: The HPA Lag Problem, Hybrid Architectural Justification, Complete Tech Stack, and 100% Cloud Enterprise Roadmap", sub_style))
    
    # Metadata Table
    meta_data = [
        [Paragraph("<b>Project Name:</b> BurstOps (Layer-7 Elastic Burst Gateway)", body_style),
         Paragraph("<b>Document Status:</b> Master Architecture Specification", body_style)],
        [Paragraph("<b>Current Implementation:</b> Option A Hybrid (Local K8s + Azure Serverless)", body_style),
         Paragraph("<b>Target Cloud Platform:</b> Microsoft Azure (centralindia)", body_style)],
        [Paragraph("<b>Active Azure Subscription:</b> Azure for Students (c6e32bdf-..., Enabled)", body_style),
         Paragraph("<b>Target Production Roadmap:</b> 100% Cloud Enterprise (AKS + ACR + Functions)", body_style)]
    ]
    t_meta = Table(meta_data, colWidths=[252, 252])
    t_meta.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), c_bg_light),
        ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor("#E2E8F0")),
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
        ('LEFTPADDING', (0,0), (-1,-1), 6),
        ('RIGHTPADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(t_meta)
    story.append(Spacer(1, 6))
    
    # Executive Summary
    story.append(Paragraph("Executive Summary", h2_style))
    story.append(Paragraph(
        "BurstOps is an asynchronous, Layer-7 intelligent reverse proxy and traffic deflection gateway engineered to eliminate the "
        "Kubernetes Horizontal Pod Autoscaler (HPA) Provisioning Lag. In modern cloud-native architectures, sudden, unpredictable traffic "
        "spikes cause container CPU utilization to instantly saturate. Although Kubernetes HPA is configured to autoscale pods, there is a "
        "fundamental, unavoidable delay of 60 to 90+ seconds between the onset of a spike and the moment newly scheduled pods pass readiness probes "
        "and register with the Service endpoints. During this window—the 'Meltdown Window'—existing pods experience CPU starvation, socket buffer "
        "exhaustion, request queue overflow, and cascading HTTP 504 Gateway Timeouts.<br/><br/>"
        "BurstOps acts as an operational shock absorber that does NOT replace HPA, but rather buys HPA the time it needs to scale. "
        "The instant cluster CPU crosses an operational threshold (80%), BurstOps dynamically deflects excess baseline traffic to public cloud serverless "
        "compute (Azure Functions on Flex Consumption) using sub-millisecond Proportional-Integral (PI) control and cryptographic HMAC-SHA256 authentication. "
        "Once HPA brings new pods online and cluster CPU recovers below 60%, BurstOps smoothly reduces deflection back to zero, returning 100% of traffic "
        "to on-cluster resources.", body_style
    ))
    
    # 1. Problem Statement
    story.append(Paragraph("1. Detailed Problem Statement & Real-World Failure Modes", h1_style))
    story.append(Paragraph("1.1 The Anatomy of the 60 to 90+ Second HPA Provisioning Lag", h2_style))
    story.append(Paragraph(
        "In modern containerized microservice architectures, Kubernetes Horizontal Pod Autoscaler (HPA) is the de-facto industry standard "
        "for dynamically scaling application workloads based on CPU and memory utilization. However, despite its widespread adoption, "
        "HPA suffers from a fundamental, unavoidable architectural bottleneck: <b>Provisioning Lag</b>.<br/><br/>"
        "When an unexpected, abrupt traffic spike occurs (e.g. flash sales, viral social surges, black friday checkout spikes, or batch job bursts), "
        "Kubernetes cannot react instantaneously. The autoscaling pipeline introduces compounding delays across multiple discrete stages:<br/><br/>"
        "<b>1. Metrics Scraping Window (15–30 seconds):</b> Scrapers (Metrics Server, Prometheus, or cAdvisor) sample container cgroups periodically and calculate sliding-window rates (e.g. rate(container_cpu_usage_seconds_total[30s])) to prevent thrashing.<br/>"
        "<b>2. HPA Evaluation Loop (15 seconds):</b> By default, the Kubernetes kube-controller-manager evaluates HPA scaling algorithms every 15 seconds.<br/>"
        "<b>3. Scheduling Latency (5–10 seconds):</b> The Kubernetes API server and kube-scheduler must identify available nodes with sufficient CPU/memory requests, bind the pod to a worker node, and update cluster etcd state.<br/>"
        "<b>4. Image Pulling & Unpacking (10–30+ seconds):</b> Even when images are cached, container runtime engines (containerd / CRI-O) must unpack layer tarballs, allocate overlay filesystems, and attach network namespaces.<br/>"
        "<b>5. Language Runtime Bootstrap & Readiness Probes (15–30 seconds):</b> High-level application frameworks (Python ASGI, Java Spring Boot, Node.js) take several seconds to import libraries, compile bytecode, establish database connection pools, and pass readinessProbe HTTP health checks before Kube-Proxy registers the pod into the Service VIP.", body_style
    ))
    
    # PageBreak so Section 1.2 starts cleanly on Page 2
    story.append(PageBreak())
    
    story.append(Paragraph("1.2 The Production Consequence: The 'Meltdown Window'", h2_style))
    story.append(Paragraph(
        "During these 60 to 90+ seconds, existing pods bear the full brunt of the traffic surge. This triggers a cascading collapse:<br/>"
        "• <b>CPU Starvation:</b> Worker threads spend 100% of their cycles in context switching or CPU-bound loops, starving asynchronous event loops.<br/>"
        "• <b>TCP Socket Buffer Exhaustion:</b> The Linux socket listen backlog (somaxconn) and TCP accept queue fill completely; ingress proxies fail to establish TCP handshakes.<br/>"
        "• <b>Cascading HTTP Timeouts:</b> Upstream reverse proxies (Nginx Ingress, AWS ALB, Azure App Gateway, Cloudflare) exceed timeout thresholds, returning HTTP 504 Gateway Timeout and HTTP 502 Bad Gateway to end users.<br/>"
        "• <b>Liveness Probe Death Spiral:</b> Overloaded pods fail to respond to Kubernetes /healthz liveness probes. Kubelet interprets this as an application deadlock, forcibly killing pods with SIGKILL. The resulting CrashLoopBackOff cycle reduces cluster capacity further, ensuring total system collapse.", body_style
    ))
    
    story.append(Paragraph("1.3 Why Naive Alternatives Fail in Production", h2_style))
    story.append(Paragraph(
        "• <b>Lowering HPA CPU Target (e.g. from 80% to 40%):</b> Leads to permanent cluster over-provisioning, wasting thousands of dollars in idle cloud compute during off-peak hours, yet still fails when a sudden 10x surge arrives faster than the 90-second spin-up time.<br/>"
        "• <b>Pre-Provisioning Massive VM Reserve Pools:</b> Economically unviable and antithetical to cloud-native elasticity. Idle VMs in Virtual Machine Scale Sets accrue full hourly charges, OS disk fees, and load balancer costs.<br/>"
        "• <b>Aggressive 24/7 Pod Over-Provisioning:</b> Running 10-20 idle pod replicas permanently is a FinOps disaster for any cost-conscious engineering organization.", body_style
    ))
    
    # Callout Box: Solution Thesis
    callout_data = [[
        Paragraph("📌 <b>CORE PROBLEM STATEMENT & SOLUTION</b>", callout_title_style),
    ], [
        Paragraph("• <b>The BurstOps Thesis:</b> BurstOps does NOT replace HPA; it acts as an operational shock absorber that <b>BUYS HPA TIME</b>.<br/>"
                  "• <b>Core Objective:</b> The instant CPU crosses 80%, deflect overflow traffic to serverless functions in milliseconds.<br/>"
                  "• <b>Outcome:</b> Zero dropped requests, sub-second p95 response times, and zero pod crashes while HPA brings new pods online.", callout_body_style)
    ]]
    t_callout = Table(callout_data, colWidths=[504])
    t_callout.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#F0F4F8")),
        ('LINELEFT', (0,0), (0,-1), 3, c_primary),
        ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('LEFTPADDING', (0,0), (-1,-1), 8),
        ('RIGHTPADDING', (0,0), (-1,-1), 8),
    ]))
    story.append(t_callout)
    story.append(Spacer(1, 8))

    # 2. System Architecture & Diagram
    story.append(Paragraph("2. Complete System Architecture & Interaction Model", h1_style))
    story.append(Paragraph(
        "Below is the complete architectural topology and interaction blueprint of the BurstOps system, detailing the relationships "
        "between clients, gateway control logic, telemetry pipelines, cloud integration, operations, and compute backends:", body_style
    ))
    
    # EMBED DIAGRAM ON ITS OWN CLEAN PAGE
    story.append(PageBreak())
    img_path = "/Users/rajmishara/burstOps/docs/architecture/system_architecture_diagram.png"
    if os.path.exists(img_path):
        story.append(Image(img_path, width=6.5*inch, height=4.3*inch))
        story.append(Paragraph("Figure 1: BurstOps Master System Architecture Diagram (Gateway Control, Telemetry State, Cloud Integration, Operations & Compute)", caption_style))
        
    story.append(Paragraph("2.1 Subsystem Breakdown & Component Interactions", h2_style))
    story.append(Paragraph(
        "<b>1. Gateway Control Subsystem (gateway.py):</b><br/>"
        "• <b>Gateway API:</b> Asynchronous Layer-7 reverse proxy built with FastAPI and Uvicorn. Handles incoming /calculate requests and distributes traffic.<br/>"
        "• <b>CPU Poller:</b> Dedicated background daemon polling Prometheus metrics every 2.0 seconds.<br/>"
        "• <b>Routing State Engine:</b> Evaluates the hysteresis finite state machine (80% Burst / 60% Recovery) to prevent route flapping.<br/>"
        "• <b>PI Controller:</b> Continuous Proportional-Integral controller computing dynamic deflection ratio r(t) with anti-windup clamping [0.0, 1.0].<br/>"
        "• <b>HMAC Signer:</b> Cryptographic signer generating HMAC-SHA256 digests over timestamps and request bodies for cloud requests.<br/><br/>"
        "<b>2. Telemetry State Subsystem:</b><br/>"
        "• <b>Prometheus (prometheus.yml):</b> Time-series metrics engine scraping cAdvisor, cpu-sim, and gateway metrics on a 2s cadence.<br/>"
        "• <b>CPU Simulator (app.py):</b> PromQL-compatible synthetic metrics generator allowing deterministic testing with inertia glide curves.<br/>"
        "• <b>Redis Backplane (redis_backplane.py):</b> High-performance distributed coordination store for multi-replica leader lease and pub/sub state broadcasting.<br/><br/>"
        "<b>3. Cloud Integration Subsystem:</b><br/>"
        "• <b>Azure Function (function_app.py):</b> Production serverless burst target running on Azure Flex Consumption (Python 3.13 in Central India).<br/>"
        "• <b>Local Function (dummy-serverless/app.py):</b> Offline local serverless stand-in with 50-150ms artificial latency injection for local testing.<br/>"
        "• <b>HMAC Verifier (hmac_util.py):</b> Timing-safe verifier checking x-functions-key, x-gateway-timestamp, and x-gateway-signature.<br/><br/>"
        "<b>4. Operations Subsystem:</b><br/>"
        "• <b>Grafana Dashboard (burstops.json):</b> Real-time 12-panel dashboard tracking routing mode, CPU curve, deflection ratio, and FinOps metrics.<br/>"
        "• <b>Cost Model (costing.py):</b> Evaluates cloud unit economics, serverless invocation premiums, and the 28.55 RPS breakeven boundary.<br/>"
        "• <b>Tracing Hooks (tracing.py):</b> Injects W3C traceparent distributed context with adaptive sampling (100% burst / 5% baseline).<br/>"
        "• <b>Trace Collector:</b> OTLP collector ingesting distributed spans.<br/><br/>"
        "<b>5. Request Compute Subsystem:</b><br/>"
        "• <b>Backend VIP (nginx.conf):</b> Nginx reverse proxy simulating a Kubernetes ClusterIP Service, balancing round-robin between worker pods.<br/>"
        "• <b>Kubernetes Backend (dummy-backend/app.py):</b> Pod replicas executing the deterministic Sieve of Eratosthenes prime calculation canary.", body_style
    ))
    
    story.append(PageBreak())

    # 3. Technologies Used & Why
    story.append(Paragraph("3. Technologies Used & Architectural Justifications", h1_style))
    story.append(Paragraph(
        "Every single library, engine, and cloud component in BurstOps was selected after evaluating production trade-offs:", body_style
    ))
    
    tech_data = [
        [Paragraph("<b>Technology / Tool</b>", callout_title_style),
         Paragraph("<b>Role in Project</b>", callout_title_style),
         Paragraph("<b>Why We Used It (Architectural Justification)</b>", callout_title_style)],
        [Paragraph("FastAPI & Uvicorn", body_style), Paragraph("Layer-7 Gateway Router", body_style), Paragraph("Asynchronous ASGI execution gives high throughput and sub-millisecond routing overhead with <50MB RAM footprint.", body_style)],
        [Paragraph("Nginx (1.27-Alpine)", body_style), Paragraph("Backend VIP / Load Balancer", body_style), Paragraph("Industry standard for high-performance TCP/HTTP reverse proxying; faithfully simulates Kubernetes ClusterIP Service round-robin balancing.", body_style)],
        [Paragraph("Prometheus (v2.53)", body_style), Paragraph("Metrics Engine & Scraper", body_style), Paragraph("Pull-based metrics collection with standard PromQL query evaluation; accurately models real-world 30-second sliding rate windows.", body_style)],
        [Paragraph("Redis 7 (Alpine)", body_style), Paragraph("Distributed State & Lock", body_style), Paragraph("Sub-millisecond memory performance; native Lua scripting engine enables atomic Compare-And-Set (CAS) leader election without external dependencies.", body_style)],
        [Paragraph("Grafana (v11.1.4)", body_style), Paragraph("Observability Dashboard", body_style), Paragraph("Real-time visual monitoring with declarative JSON provisioning; allows live visualization of routing mode, CPU curve, deflection ratio, and FinOps gauges.", body_style)],
        [Paragraph("Azure Functions (Flex Consumption)", body_style), Paragraph("Cloud Serverless Burst Target", body_style), Paragraph("Sub-second container cold-starts, instantaneous auto-concurrency, zero idle compute costs, and 1,000,000 free monthly executions under Azure for Students.", body_style)],
        [Paragraph("Azure Application Insights", body_style), Paragraph("Distributed Cloud Telemetry", body_style), Paragraph("Deep serverless telemetry; provides automatic Application Map topology, latency percentile distribution, and real-time QuickPulse streaming with strict 0.15 GB/day budget caps.", body_style)],
        [Paragraph("Terraform (IaC)", body_style), Paragraph("Cloud Infrastructure as Code", body_style), Paragraph("Declarative, repeatable cloud infrastructure provisioning; automates secret generation (HMAC keys) and provisions resource groups, storage, and budgets without manual portal drift.", body_style)],
        [Paragraph("HMAC-SHA256 Cryptography", body_style), Paragraph("Inter-Cloud Security Protocol", body_style), Paragraph("Timing-safe cryptographic signature over timestamp and body; rejects tampered payloads and replays (>300s) without the complexity and latency of mTLS.", body_style)],
        [Paragraph("Pytest & Coverage", body_style), Paragraph("Invariant Testing Suite", body_style), Paragraph("Automated formal verification; 89 test cases guarantee mathematical correctness across hysteresis state transitions, HMAC security, and PI control.", body_style)]
    ]
    t_tech = Table(tech_data, colWidths=[110, 110, 284], repeatRows=1)
    t_tech.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), c_bg_light),
        ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor("#E2E8F0")),
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
        ('LEFTPADDING', (0,0), (-1,-1), 5),
        ('RIGHTPADDING', (0,0), (-1,-1), 5),
    ]))
    story.append(t_tech)
    story.append(Spacer(1, 8))

    # 4. Project Workflow & End-to-End Operational Lifecycle
    story.append(Paragraph("4. Comprehensive Project Workflow & Operational Lifecycle", h1_style))
    story.append(Paragraph(
        "BurstOps operates as an autonomous, closed-loop cybernetic feedback system. Rather than viewing the architecture "
        "as a static set of components, its real-world implementation is best understood through its five-stage continuous operational workflow:", body_style
    ))
    
    wf_img = "/Users/rajmishara/burstOps/docs/architecture/burstops_workflow_diagram.png"
    if os.path.exists(wf_img):
        story.append(Image(wf_img, width=6.5*inch, height=3.6*inch))
        story.append(Paragraph("Figure 2: BurstOps 5-Stage Closed-Loop Operational Workflow Diagram", caption_style))
        story.append(Spacer(1, 4))
        
    story.append(Paragraph("4.1 Stage 1: Ingestion, Traffic Classification & Steady-State Routing", h2_style))
    story.append(Paragraph(
        "• <b>Client Ingestion:</b> Incoming Layer-7 HTTP requests (/calculate) from clients arrive at the asynchronous BurstOps reverse proxy gateway (FastAPI ASGI).<br/>"
        "• <b>Baseline Operational Regime:</b> While cluster CPU remains below saturation (CPU < 80%), the routing state machine maintains BASELINE MODE with deflection ratio r(t) = 0.0.<br/>"
        "• <b>Cluster VIP Dispatch:</b> 100% of client traffic is routed internally to the on-cluster Virtual IP (Nginx ClusterIP Service simulator), balancing across worker pods.<br/>"
        "• <b>Canary Execution:</b> Worker pods execute the CPU-bound Sieve of Eratosthenes over [2..1000] (168 primes, sum 76,127), establishing deterministic compute baselines.", body_style
    ))
    
    story.append(Paragraph("4.2 Stage 2: High-Frequency Telemetry Sampling & Inertia Sensing", h2_style))
    story.append(Paragraph(
        "• <b>Continuous Metrics Scraping:</b> An asynchronous background daemon queries Prometheus on an aggressive 2.0-second sampling cycle.<br/>"
        "• <b>Sliding-Window Rate Evaluation:</b> Telemetry evaluates PromQL expressions: rate(container_cpu_usage_seconds_total[30s]), filtering out instantaneous sub-second noise while reliably capturing sustained surges.<br/>"
        "• <b>Inertia Simulation:</b> Synthetic CPU simulator models hardware thermal and processing inertia curves, allowing repeatable benchmarking without OS variance.", body_style
    ))
    
    story.append(Paragraph("4.3 Stage 3: Distributed Closed-Loop Decision Engine & Consensus", h2_style))
    story.append(Paragraph(
        "• <b>Redis Backplane:</b> Gateways coordinate via Redis 7 to support horizontal scaling without creating a thundering herd on Prometheus.<br/>"
        "• <b>Atomic Lua CAS Leader Election:</b> Exactly one gateway replica is elected leader to poll Prometheus and execute control algorithms.<br/>"
        "• <b>Asymmetric Hysteresis State Machine:</b> Switches to BURST MODE at CPU >= 80%, and returns to RECOVERY MODE only below 60%. The 20% gap eliminates route flapping.<br/>"
        "• <b>Continuous PI Deflection Math:</b> r(t) = clamp(Kp*e(t) + Ki*∫e(t)dt, 0.0, 1.0) with anti-windup clamping and slew-rate limiting (0.10/s).<br/>"
        "• <b>Zero-Latency In-Memory Sync:</b> Leader broadcasts r(t) over Redis Pub/Sub; followers update in-memory cache (<0.05ms) with zero Redis I/O on the request path.", body_style
    ))
    
    story.append(Paragraph("4.4 Stage 4: Cryptographic Zero-Trust Deflection & Serverless Execution", h2_style))
    story.append(Paragraph(
        "• <b>Proportional Traffic Splitting:</b> Fraction (1 - r(t)) remains on cluster; overflow fraction r(t) is deflected to serverless compute.<br/>"
        "• <b>HMAC-SHA256 Wire Cryptography:</b> Deflected requests are signed with an HMAC-SHA256 digest over the timestamp and body, eliminating mTLS complexity.<br/>"
        "• <b>Timing-Safe Cloud Verification:</b> Azure Function (Flex Consumption in Central India) verifies signatures using constant-time comparison and enforces a 300s replay window.<br/>"
        "• <b>Millisecond Elastic Scale:</b> Serverless compute instances scale out instantly with $0.00 idle cost and 1,000,000 free monthly executions.", body_style
    ))
    
    story.append(Paragraph("4.5 Stage 5: Autonomous Surge Absorption, HPA Convergence & Recovery", h2_style))
    story.append(Paragraph(
        "• <b>Absorbing the 90s Lag Window:</b> BurstOps absorbs overflow while Kubernetes HPA completes its multi-stage spin-up lifecycle.<br/>"
        "• <b>Cluster Capacity Multiplication:</b> As new pods pass readiness probes, cluster capacity multiplies and CPU drops below 60%.<br/>"
        "• <b>Graceful Recovery:</b> The PI controller smoothly dials r(t) back to 0.0, returning 100% of traffic to the cluster with 0 dropped connections.<br/>"
        "• <b>FinOps Reconciliation:</b> Real-time telemetry is streamed to Azure Application Insights and Grafana, while costing models reconcile spend against the 28.55 RPS breakeven boundary.", body_style
    ))
    
    story.append(PageBreak())

    # 5. Why We Did NOT Use AKS / ACR
    story.append(Paragraph("5. Architectural Decision Log: Why We Did NOT Deploy AKS on Azure", h1_style))
    story.append(Paragraph(
        "A critical engineering decision in this project was choosing Option A (Hybrid Architecture: Local Kubernetes Mesh + Live Azure Serverless Target) "
        "instead of deploying a full Azure Kubernetes Service (AKS) cluster and Azure Container Registry (ACR) on Azure. Below is the transparent architectural rationale:", body_style
    ))
    story.append(Paragraph("5.1 The Financial Reality of Azure for Students Subscriptions", h2_style))
    story.append(Paragraph(
        "Azure for Students provides a fixed $100 one-time annual credit with strict non-renewable quota boundaries. Unlike enterprise corporate "
        "subscriptions with monthly billing accounts, student subscriptions possess zero financial buffer. Once credit is exhausted, Microsoft's automated "
        "billing guardrails immediately disable the subscription.", body_style
    ))
    story.append(Paragraph("5.2 The Continuous Cost Drain of Running an AKS Cluster", h2_style))
    story.append(Paragraph(
        "An active AKS cluster requires a Virtual Machine Scale Set (VMSS) agent node pool. Even with the smallest practical VM SKU (Standard_B2s with 2 vCPUs and 4 GiB RAM), "
        "the VMSS compute, managed OS disk storage, Public IP addresses, and Azure Load Balancer run 24 hours a day, 7 days a week.<br/>"
        "• VM Compute (Standard_B2s): ~$26.28/month<br/>"
        "• Managed OS SSD Disk (32 GB): ~$4.80/month<br/>"
        "• Standard Load Balancer & Public IP: ~$21.90/month<br/>"
        "• <b>Total Fixed Cost: ~$52.98 per month</b> — even when completely idle and serving zero traffic!<br/><br/>"
        "An active AKS cluster running continuously would exhaust the entire $100 credit pool in less than 60 days.", body_style
    ))
    story.append(Paragraph("5.3 Root Cause Analysis (RCA) of the Prior Outage", h2_style))
    story.append(Paragraph(
        "In the previous iteration of this project, a full AKS cluster (burstops-aks) and container registry (burstopsacr) were deployed on Azure. "
        "Within weeks, the idle VMSS nodes drained the entire $100 credit balance. Microsoft's automated billing guardrails immediately set the subscription state "
        "to 'Disabled', shutting down compute and returning 'HTTP 403 Site Disabled' on all endpoints. This empirical proof confirmed that running an idle "
        "Kubernetes cluster on a capped student subscription is an operational anti-pattern.", body_style
    ))
    story.append(Paragraph("5.4 The Technical & Operational Superiority of Option A (Hybrid Architecture)", h2_style))
    story.append(Paragraph(
        "• <b>Local Kubernetes Mesh (Docker Compose):</b> Replicates 100% of Kubernetes pod networking, Nginx ClusterIP VIP round-robin balancing, and cAdvisor metric scraping at $0.00 cost.<br/>"
        "• <b>Live Azure Serverless Target (Flex Consumption):</b> Real public cloud execution, real internet boundary traversal, real HMAC cryptographic authentication, and real Azure Application Insights telemetry. "
        "Because Flex Consumption charges strictly per millisecond of execution ($0.00 when idle, with 1,000,000 free monthly executions), it provides 100% of the verification proof with zero credit drain.", body_style
    ))
    
    # Callout Box: Cost Discipline
    callout_cost = [[
        Paragraph("📌 <b>COST DISCIPLINE & ARCHITECTURAL PRUDENCE</b>", callout_title_style),
    ], [
        Paragraph("• <b>Strategic Decision:</b> Option A delivered 100% of the educational and verification value without burning the student subscription.<br/>"
                  "• <b>Zero Compromise:</b> Real HMAC signing, real internet hops to Central India, and real Azure Portal telemetry were all proven live.", callout_body_style)
    ]]
    t_callout_cost = Table(callout_cost, colWidths=[504])
    t_callout_cost.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#F0F4F8")),
        ('LINELEFT', (0,0), (0,-1), 3, c_primary),
        ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('LEFTPADDING', (0,0), (-1,-1), 8),
        ('RIGHTPADDING', (0,0), (-1,-1), 8),
    ]))
    story.append(t_callout_cost)
    story.append(Spacer(1, 8))

    # 6. Future Implementation Roadmap
    story.append(Paragraph("6. Future Implementation Roadmap: 100% Cloud Architecture & Verification", h1_style))
    story.append(Paragraph(
        "When transitioning from academic evaluation to a production enterprise deployment with a corporate Pay-As-You-Go subscription, "
        "BurstOps can be seamlessly migrated to a 100% Azure Cloud Architecture. Below is the engineering implementation blueprint:", body_style
    ))
    story.append(Paragraph("6.1 Phase 1: Cloud Infrastructure Provisioning with Terraform", h2_style))
    story.append(Paragraph(
        "• <b>Azure Kubernetes Service (AKS):</b> Provision azurerm_kubernetes_cluster with a System node pool (1x Standard_B2s for CoreDNS/Ingress) "
        "and a User node pool with auto-scaling enabled (min: 2, max: 10 nodes).<br/>"
        "• <b>Azure Container Registry (ACR):</b> Provision azurerm_container_registry (Standard SKU) with system-assigned managed identity role assignment (AcrPull) to AKS.<br/>"
        "• <b>Virtual Network (VNet) Topology:</b> Create an Azure Virtual Network with three dedicated subnets:<br/>"
        "   1. AKS Node Subnet (10.0.1.0/24)<br/>"
        "   2. Application Gateway / Ingress Subnet (10.0.2.0/24)<br/>"
        "   3. Serverless Private Endpoint Subnet (10.0.3.0/24)", body_style
    ))
    story.append(Paragraph("6.2 Phase 2: Container Packaging & CI/CD Pipeline", h2_style))
    story.append(Paragraph(
        "• Automated GitHub Actions workflow building and pushing three production container images to ACR:<br/>"
        "   - burstopsacr.azurecr.io/gateway:latest<br/>"
        "   - burstopsacr.azurecr.io/dummy-backend:latest<br/>"
        "   - burstopsacr.azurecr.io/prometheus:latest", body_style
    ))
    story.append(Paragraph("6.3 Phase 3: Kubernetes Manifest Deployment (k8s/)", h2_style))
    story.append(Paragraph(
        "• Deploy the manifests already authored in the repository:<br/>"
        "   - gateway-deployment.yaml: Deploying 3 gateway replicas with anti-affinity across AKS nodes.<br/>"
        "   - gateway-service.yaml: ClusterIP service exposing the gateway.<br/>"
        "   - ingress.yaml: Configuring Azure Application Gateway (AGIC) or Nginx Ingress Controller with SSL/TLS termination.<br/>"
        "   - hpa.yaml: Configuring the Horizontal Pod Autoscaler for the backend pods (minReplicas: 2, maxReplicas: 10, targetCPU: 70%).", body_style
    ))
    
    # Code block for HPA
    hpa_code = (
        "apiVersion: autoscaling/v2\n"
        "kind: HorizontalPodAutoscaler\n"
        "metadata:\n"
        "  name: backend-hpa\n"
        "  namespace: burstops\n"
        "spec:\n"
        "  scaleTargetRef:\n"
        "    apiVersion: apps/v1\n"
        "    kind: Deployment\n"
        "    name: backend-service\n"
        "  minReplicas: 2\n"
        "  maxReplicas: 10\n"
        "  metrics:\n"
        "  - type: Resource\n"
        "    resource:\n"
        "      name: cpu\n"
        "      target:\n"
        "        type: Utilization\n"
        "        averageUtilization: 70"
    )
    t_code = Table([[Paragraph(f"<pre>{hpa_code}</pre>", code_style)]], colWidths=[504])
    t_code.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#F8FAFC")),
        ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
        ('LEFTPADDING', (0,0), (-1,-1), 8),
        ('RIGHTPADDING', (0,0), (-1,-1), 8),
    ]))
    story.append(t_code)
    story.append(Spacer(1, 4))

    story.append(Paragraph("6.4 Phase 4: Enterprise Zero-Trust Private Networking", h2_style))
    story.append(Paragraph(
        "• Establish an Azure Private Endpoint between the AKS cluster subnet and the Azure Function (func-burstops-live).<br/>"
        "• Eliminates public internet traversal; all burst deflection flows privately across the Microsoft Azure backbone over private IP addresses (10.0.3.5) with zero exposure to public DNS.", body_style
    ))
    
    story.append(Paragraph("6.5 Phase 5: 100% Cloud Verification & Load Test Runbook", h2_style))
    story.append(Paragraph(
        "• <b>Load Generation:</b> Deploy distributed Locust workers via Azure Container Instances (ACI) generating 1,000+ concurrent RPS against the public Ingress IP.<br/>"
        "• <b>Verification Metric 1 (HPA Scale-Out):</b> Execute 'kubectl get hpa -w' to observe the 90-second pod scale-out window (pods scaling from 2 to 10).<br/>"
        "• <b>Verification Metric 2 (Burst Deflection Correlation):</b> In Azure Application Insights, correlate the exact 90-second HPA lag window with serverless invocation spikes.<br/>"
        "• <b>Verification Metric 3 (Surge Absorption & Stabilization):</b> As new AKS pods reach Ready status, observe the BurstOps gateway automatically reducing the deflection ratio r(t) back to 0.0%.<br/>"
        "• <b>Verification Metric 4 (Cloud FinOps Reconciliation):</b> In Azure Cost Management, reconcile the total cost of serverless invocations versus AKS compute hours to validate the 28.55 RPS breakeven formula in production.", body_style
    ))
    
    # Callout Box: Future Readiness
    callout_future = [[
        Paragraph("📌 <b>FUTURE CLOUD READINESS</b>", callout_title_style),
    ], [
        Paragraph("• <b>Ready for Enterprise Cloud:</b> All Kubernetes manifests (k8s/) and Terraform definitions already exist in the codebase.<br/>"
                  "• <b>Direct Transition Path:</b> Migrating to 100% cloud requires only running 'terraform apply' on a funded subscription.", callout_body_style)
    ]]
    t_callout_future = Table(callout_future, colWidths=[504])
    t_callout_future.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#F0F4F8")),
        ('LINELEFT', (0,0), (0,-1), 3, c_primary),
        ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('LEFTPADDING', (0,0), (-1,-1), 8),
        ('RIGHTPADDING', (0,0), (-1,-1), 8),
    ]))
    story.append(t_callout_future)
    
    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"Spec PDF successfully built at {pdf_path} (Size: {os.path.getsize(pdf_path):,} bytes)")

if __name__ == "__main__":
    build_pdf()
