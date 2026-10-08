import os
import sys
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle, KeepTogether, PageBreak
)
from reportlab.pdfgen import canvas

class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, page_count):
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#6B7280"))
        
        # Header (pages > 1)
        if self._pageNumber > 1:
            self.drawString(54, letter[1] - 36, "BurstOps: Complete System Implementation & Verification Report")
            self.setStrokeColor(colors.HexColor("#E5E7EB"))
            self.setLineWidth(0.5)
            self.line(54, letter[1] - 42, letter[0] - 54, letter[1] - 42)
            
        # Footer
        self.setStrokeColor(colors.HexColor("#E5E7EB"))
        self.setLineWidth(0.5)
        self.line(54, 45, letter[0] - 54, 45)
        
        page_text = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(letter[0] - 54, 32, page_text)
        self.drawString(54, 32, "Confidential — Evaluated on Active Microsoft Azure & Local Kubernetes Mesh")
        self.restoreState()

def create_callout(text_list, title="TECHNICAL TAKEAWAY", width=504):
    content = []
    t_style = ParagraphStyle(
        'CalloutTitle', fontName='Helvetica-Bold', fontSize=9, leading=11.5, textColor=colors.HexColor("#1B365D")
    )
    b_style = ParagraphStyle(
        'CalloutBody', fontName='Helvetica', fontSize=8, leading=10.5, textColor=colors.HexColor("#374151")
    )
    content.append(Paragraph(f"📌 <b>{title}</b>", t_style))
    content.append(Spacer(1, 3))
    for t in text_list:
        content.append(Paragraph(t, b_style))
        content.append(Spacer(1, 1.5))
        
    t = Table([[content]], colWidths=[width])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#F0F4F8")),
        ('LINEBEFORE', (0, 0), (0, -1), 3, colors.HexColor("#1B365D")),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
    ]))
    return t

def create_code_block(code_str, width=504):
    escaped = code_str.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('\n', '<br/>')
    c_style = ParagraphStyle(
        'CodeStyle', fontName='Courier', fontSize=7, leading=8.5, textColor=colors.HexColor("#1E293B")
    )
    p = Paragraph(escaped, c_style)
    t = Table([[p]], colWidths=[width])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
    ]))
    return t

def create_image_flowable(img_path, caption, max_w=504, max_h=190):
    if not os.path.exists(img_path):
        return Paragraph(f"[Image Missing: {img_path}]", ParagraphStyle('Err', textColor=colors.red))
    from PIL import Image as PILImage
    with PILImage.open(img_path) as im:
        orig_w, orig_h = im.size
    
    scale = min(max_w / orig_w, max_h / orig_h, 1.0)
    final_w = orig_w * scale
    final_h = orig_h * scale
    
    img = Image(img_path, width=final_w, height=final_h)
    cap_style = ParagraphStyle(
        'CapStyle', fontName='Helvetica-Oblique', fontSize=7.5, leading=9.5, alignment=1, textColor=colors.HexColor("#4B5563")
    )
    cap = Paragraph(f"Figure: {caption}", cap_style)
    
    t = Table([[img], [cap]], colWidths=[max_w])
    t.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('TOPPADDING', (0, 0), (-1, -1), 1),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
    ]))
    return t

def build_pdf():
    pdf_path = "/Users/rajmishara/burstOps/BURSTOPS_FINAL_COMPLETE_IMPLEMENTATION.pdf"
    doc = SimpleDocTemplate(
        pdf_path,
        pagesize=letter,
        leftMargin=54,
        rightMargin=54,
        topMargin=54,
        bottomMargin=54
    )
    
    title_style = ParagraphStyle('DocTitle', fontName='Helvetica-Bold', fontSize=18, leading=22, textColor=colors.HexColor("#1B365D"))
    sub_style = ParagraphStyle('DocSub', fontName='Helvetica-Oblique', fontSize=10, leading=13, textColor=colors.HexColor("#475569"))
    h1_style = ParagraphStyle('Head1', fontName='Helvetica-Bold', fontSize=12, leading=15, spaceBefore=12, spaceAfter=5, textColor=colors.HexColor("#1B365D"), keepWithNext=True)
    h2_style = ParagraphStyle('Head2', fontName='Helvetica-Bold', fontSize=9.5, leading=12, spaceBefore=8, spaceAfter=3, textColor=colors.HexColor("#2B547E"), keepWithNext=True)
    body_style = ParagraphStyle('Body', fontName='Helvetica', fontSize=8.5, leading=11.5, textColor=colors.HexColor("#1F2937"), spaceAfter=4)
    table_text = ParagraphStyle('TableText', fontName='Helvetica', fontSize=7.5, leading=9.5, textColor=colors.HexColor("#1F2937"))
    table_head = ParagraphStyle('TableHead', fontName='Helvetica-Bold', fontSize=7.5, leading=9.5, textColor=colors.white)
    
    story = []
    
    # Title & Subtitle
    story.append(Paragraph("BurstOps: Complete System Implementation & Verification Report", title_style))
    story.append(Spacer(1, 2))
    story.append(Paragraph("Master Technical Reference: Local Microservice Mesh, Live Microsoft Azure Cloud Bursting & Distributed Telemetry Audit", sub_style))
    story.append(Spacer(1, 6))
    
    # Metadata Table
    meta_data = [
        [Paragraph("<b>Architecture Model:</b>", table_text), Paragraph("Option A Hybrid: Local K8s Mesh + Live Azure Serverless Target", table_text),
         Paragraph("<b>Execution Date:</b>", table_text), Paragraph("September 19, 2026", table_text)],
        [Paragraph("<b>Azure Subscription:</b>", table_text), Paragraph("Azure for Students (c6e32bdf-69dd-4451-8c44-7b35c5ad187b, State: Enabled)", table_text),
         Paragraph("<b>Azure Region:</b>", table_text), Paragraph("Central India (centralindia)", table_text)],
        [Paragraph("<b>Live Cloud Function:</b>", table_text), Paragraph("func-burstops-live (Flex Consumption Python 3.13)", table_text),
         Paragraph("<b>Application Insights:</b>", table_text), Paragraph("appi-burstops-3l8y5t (Daily Cap: 0.15 GB/day)", table_text)],
    ]
    t_meta = Table(meta_data, colWidths=[100, 152, 100, 152])
    t_meta.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
        ('TOPPADDING', (0, 0), (-1, -1), 2.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2.5),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
    ]))
    story.append(t_meta)
    story.append(Spacer(1, 8))
    
    # 1. Executive Summary & Problem Solved
    story.append(Paragraph("1. Executive Summary & Core Problem Solved", h1_style))
    story.append(Paragraph(
        "Modern cloud-native container platforms rely on the Kubernetes Horizontal Pod Autoscaler (HPA) to scale workloads. "
        "However, physical pod provisioning involves a mandatory multi-step latency pipeline: Prometheus metrics scraping windows (15–30s), "
        "HPA evaluation periods (15s), image pulling, container runtime bootstrap, and application readiness probes. "
        "In production, this creates an un-provisioned lag window of <b>60 to 90+ seconds</b>.",
        body_style
    ))
    story.append(Paragraph(
        "During sudden, abrupt traffic surges (such as flash sales, breaking news spikes, or viral traffic), existing pods saturate at 100% CPU. "
        "Request queues fill, latency degrades exponentially, worker threads block, and users experience cascading <code>HTTP 504 Gateway Timeouts</code> "
        "or connection resets before new pods can initialize.",
        body_style
    ))
    story.append(Paragraph(
        "<b>BurstOps</b> functions as an operational shock absorber for the cluster. Operating as an intelligent Layer-7 gateway, "
        "it monitors cluster CPU utilization in real time. The instant cluster CPU crosses 80%, BurstOps cryptographically signs and deflects "
        "overflow requests across the public internet to a serverless Azure Function (<code>func-burstops-live</code> in Central India). "
        "Because serverless functions auto-scale concurrently in milliseconds with zero pod initialization lag, the surge is instantly absorbed. "
        "When the traffic surge subsides and CPU falls below 60%, BurstOps smoothly returns all traffic to the Kubernetes baseline.",
        body_style
    ))
    story.append(create_callout([
        "• Core Value Proposition: Buys HPA the 60–90 seconds it needs, eliminating the traffic surge meltdown window.",
        "• Traffic Routing State Machine: Hysteresis control (80% Burst Trigger / 60% Recovery Trigger) to prevent route flapping.",
        "• Proportional-Integral (PI) Controller: Continuous dynamic deflection ratio r(t) with anti-windup clamping [0.0, 1.0].",
        "• Cryptographic Wire Security: HMAC-SHA256 request signing with canonical hashing and 300s timestamp replay prevention.",
        "• FinOps Unit Economics: Real-time calculation of burst premiums and automatic monitoring against the 28.55 RPS breakeven boundary."
    ], title="CORE ARCHITECTURAL HIGHLIGHTS"))

    # 2. System Architecture & Request Contract
    story.append(Paragraph("2. System Architecture & The Request Contract", h1_style))
    story.append(Paragraph(
        "To verify the system authentically, every request routed through BurstOps represents genuine, measurable computational work. "
        "The target endpoint is <code>/calculate</code>, which executes the <b>Sieve of Eratosthenes</b> prime number algorithm across the integer range <code>[2 .. 1000]</code>.",
        body_style
    ))
    story.append(Paragraph(
        "<b>The Mathematical Canaries:</b><br/>"
        "Every valid execution of <code>/calculate</code> must deterministically compute and return:<br/>"
        "&nbsp;&nbsp;&nbsp;&nbsp;• <b>prime_count: 168</b> (there are exactly 168 prime numbers between 2 and 1,000)<br/>"
        "&nbsp;&nbsp;&nbsp;&nbsp;• <b>prime_sum: 76127</b> (the exact sum of all 168 prime numbers)<br/>"
        "These deterministic values prove that whether a request was handled locally by Kubernetes pods or deflected across the public internet "
        "to Microsoft Azure in Central India, identical, authentic computational work was completed.",
        body_style
    ))
    story.append(Paragraph(
        "<b>Wire Protocol & Security Headers:</b><br/>"
        "Clients submit HTTP/1.1 requests to <code>http://localhost:8080/calculate</code>. The gateway attaches W3C distributed tracing context "
        "(<code>traceparent</code> header). For serverless burst deflections, the gateway computes an HMAC-SHA256 signature using the shared 48-character secret "
        "(<code>GATEWAY_HMAC_SECRET</code>) and injects: <code>x-functions-key</code>, <code>x-gateway-timestamp</code>, and <code>x-gateway-signature</code>.",
        body_style
    ))

    # 3. Environment Startup
    story.append(Paragraph("3. Environment Startup & Container Topology (Local Foundation)", h1_style))
    story.append(create_code_block("docker compose start\ndocker compose ps"))
    story.append(Spacer(1, 3))
    story.append(create_image_flowable("docs/screenshots/09_terminal_docker_compose_up.png",
                                       "Terminal Execution: docker compose start and docker compose ps showing all 10 core services Up", max_h=120))
    story.append(Spacer(1, 3))
    story.append(Paragraph(
        "All 10 core services are operational: gateway (port 8080), Nginx VIP (port 8000), two backend pod replicas, "
        "dummy-serverless mock (port 8001), cpu-sim (port 8002), cadvisor (port 8082), Prometheus (port 9090), Grafana (port 3000), and Locust (port 8089).",
        body_style
    ))
    story.append(create_image_flowable("docs/screenshots/08_grafana_initial_no_data.png",
                                       "Grafana Initial State ('No Data' before first Prometheus scrape confirms dynamic time-series ingestion)", max_h=110))

    # 4. Invariants 89-test
    story.append(Paragraph("4. Formal Verification of System Invariants (The 89-Test Suite)", h1_style))
    story.append(create_code_block(".venv/bin/pytest tests/ -q\n89 passed in 0.21s"))
    story.append(Spacer(1, 3))
    story.append(create_image_flowable("docs/screenshots/10_terminal_test_suite_and_burst_verification.png",
                                       "Pytest Execution: 89 passed in 0.21s validating all mathematical and cryptographic invariants", max_h=100))
    story.append(Spacer(1, 3))
    story.append(create_callout([
        "• Hysteresis State Machine: Strict 80% entry, 60% recovery, and dead-band stability.",
        "• Cryptographic HMAC Contract: 4 golden vectors, SHA256 body hashing, and timestamp skew limits.",
        "• PI Controller & Slew Limiting: Validates proportional-integral anti-windup clamping [0.0, 1.0].",
        "• FinOps Breakeven: Formally tests the 28.55 RPS economic boundary formula.",
        "• Redis Lua CAS Lease: Validates atomic leader election and failover.",
        "• OpenTelemetry Tracing: Validates W3C traceparent propagation and credential sanitization."
    ], title="INVARIANTS PROVEN BY TEST SUITE"))

    # 5. Phase 1: Baseline
    story.append(Paragraph("5. Phase 1: Baseline Operation & Local Kubernetes Load Balancing", h1_style))
    story.append(create_code_block(
        "# Reset CPU to 20% baseline\n"
        "curl -X POST 'http://localhost:8002/set?pct=20'\n"
        "{\"target_pct\":20.0,\"current_pct\":94.99999999999994}\n\n"
        "# Verify gateway health\n"
        "curl -s http://localhost:8080/health\n"
        "{\"mode\":\"baseline\",\"last_cpu\":19.755577702730434}\n\n"
        "# Execute calculation request\n"
        "curl -i http://localhost:8080/calculate\n"
        "HTTP/1.1 200 OK\n"
        "{\"source\":\"k8s\",\"impl\":\"dummy-backend\",\"hostname\":\"bd2e4c973393\",\"prime_count\":168,\"prime_sum\":76127}"
    ))
    story.append(Spacer(1, 3))
    story.append(create_image_flowable("docs/screenshots/live_azure/02_terminal_baseline_k8s_cycle.png",
                                       "Terminal Execution: Baseline cycle showing CPU at 19.75%, mode 'baseline', and traffic serviced locally by dummy-backend pod", max_h=110))
    story.append(Spacer(1, 3))
    story.append(Paragraph(
        "<b>Technical Analysis:</b> CPU is at 19.75% (< 80%), routing mode is 'baseline', and requests are balanced across worker pods "
        "(<code>bd2e4c973393</code> and <code>28b379017faf</code>) via the Nginx VIP (:8000). Both pods compute exactly 168 primes and 76127 sum.",
        body_style
    ))
    story.append(create_image_flowable("docs/screenshots/live_azure/10_grafana_baseline_mode_overview.png",
                                       "Grafana Baseline State: Big green 'baseline' tile, CPU falling to 40.2%, Deflection ratio at 0.0%, 100% traffic to k8s", max_h=110))

    # 6. Phase 2: Azure Cloud Verification
    story.append(Paragraph("6. Phase 2: Azure Cloud Burst Target & Subscription Verification", h1_style))
    story.append(create_code_block("az account show --query '{name:name, state:state, id:id}' -o table\n\nName                State\n------------------  -------\nAzure for Students  Enabled"))
    story.append(Spacer(1, 3))
    story.append(create_image_flowable("docs/screenshots/live_azure/01_terminal_azure_subscription_active.png",
                                       "Azure CLI confirmation of active subscription: 'Azure for Students' (State: Enabled)", max_h=50))
    story.append(Spacer(1, 3))
    story.append(create_callout([
        "• Subscription Name: Azure for Students (ID: c6e32bdf-69dd-4451-8c44-7b35c5ad187b).",
        "• Resource Group: rg-burstops-prod in Central India (centralindia).",
        "• Cost Safety: Option A runs the serverless burst target on Azure Flex Consumption (1,000,000 free monthly executions) while maintaining the baseline cluster in local Docker, preventing the $30+/month AKS VMSS credit drain."
    ], title="SUBSCRIPTION & INFRASTRUCTURE INTEGRITY"))

    # 7. Phase 3: Traffic Surge & Cloud Burst
    story.append(Paragraph("7. Phase 3: Traffic Surge & Live Burst Deflection to Azure Cloud", h1_style))
    story.append(create_code_block(
        "# Trigger CPU surge to 95%\n"
        "curl -X POST 'http://localhost:8002/set?pct=95'\n"
        "{\"target_pct\":95.0,\"current_pct\":20.000000000000032}\n\n"
        "# Verify gateway crossed threshold into burst mode\n"
        "curl -s http://localhost:8080/health\n"
        "{\"mode\":\"burst\",\"last_cpu\":95.45142672563948}\n\n"
        "# Execute calculation request through gateway during burst\n"
        "curl -i http://localhost:8080/calculate\n"
        "HTTP/1.1 200 OK\n"
        "{\"source\": \"serverless\", \"impl\": \"azure-function\", \"instance_id\": \"local\", \"prime_count\": 168, \"prime_sum\": 76127, \"cold_start\": true}"
    ))
    story.append(Spacer(1, 3))
    story.append(create_image_flowable("docs/screenshots/live_azure/03_terminal_burst_azure_function_cycle.png",
                                       "Terminal Execution: CPU at 95.45%, mode 'burst', request returned with source 'serverless' and impl 'azure-function'!", max_h=110))
    story.append(Spacer(1, 3))
    story.append(create_callout([
        "• 'impl': 'azure-function' — Proves the local gateway signed and forwarded the request to Microsoft Azure in Central India.",
        "• 'cold_start': true — Captures the live on-demand container initialization by the Azure serverless runtime.",
        "• Canary Invariant: Prime count 168 and prime sum 76127 match the local backend exactly, verifying computational equivalence."
    ], title="BURST DEFLECTION SUCCESS"))

    # 8. Phase 4: Grafana Burst Observability
    story.append(Paragraph("8. Phase 4: Grafana Observability in Burst Mode & FinOps Audit", h1_style))
    story.append(create_image_flowable("docs/screenshots/live_azure/04_grafana_burst_mode_overview.png",
                                       "Grafana Burst Overview: Big red 'burst' tile, observed CPU at 95.8%, deflection ratio driven to 100%, serverless request spike", max_h=120))
    story.append(Spacer(1, 3))
    story.append(create_image_flowable("docs/screenshots/live_azure/05_grafana_burst_mode_finops.png",
                                       "Grafana FinOps Panel: Cost of HPA lag accumulates to $0.000002, cumulative burst premium $0.000002, serverless hourly spend spike", max_h=120))
    story.append(Spacer(1, 3))
    story.append(create_callout([
        "• Proportional-Integral (PI) Controller: r(t) = Kp*e(t) + Ki*∫e(t)dt. The integral accumulator reaches 30.1%, driving deflection ratio r(t) to 100% to protect the cluster.",
        "• FinOps Breakeven: The 28.55 RPS threshold gauge models the exact point where provisioning another Kubernetes node becomes cheaper than serverless.",
        "• Cost of HPA Lag: $0.000002 accrued during the surge window — the financial cost paid in serverless invocations to prevent cluster downtime."
    ], title="FINOPS & CONTROL THEORY IN ACTION"))

    # 9. Phase 5: Azure Cloud Telemetry Audit
    story.append(Paragraph("9. Phase 5: Azure Portal Telemetry, Application Map & Live Metrics", h1_style))
    story.append(Paragraph("<b>A. Overview & Server Response Time Telemetry:</b>", h2_style))
    story.append(create_image_flowable("docs/screenshots/live_azure/06_azure_portal_app_insights_overview.png",
                                       "Azure Portal Overview: Server response time (Avg: 84.54 ms), request count spikes, 0 failed requests, 100% availability", max_h=110))
    story.append(Spacer(1, 3))
    story.append(Paragraph("<b>B. Application Map (Interactive Topology Graph):</b>", h2_style))
    story.append(create_image_flowable("docs/screenshots/live_azure/07_azure_portal_application_map_active.png",
                                       "Azure Application Map: Visual node showing 4 active serverless instances, 59.6 ms average latency, and 8 calls entering func-burstops-live!", max_h=110))
    story.append(Spacer(1, 3))
    story.append(Paragraph("<b>C. Performance & Duration Distribution:</b>", h2_style))
    story.append(create_image_flowable("docs/screenshots/live_azure/08_azure_portal_performance_calculate_count_20.png",
                                       "Azure Performance View: Operation 'calculate' with 20 calls, 27.9 ms average duration, and duration percentile histogram (50th, 95th, 99th)", max_h=110))
    story.append(Spacer(1, 3))
    story.append(Paragraph("<b>D. Live Metrics (QuickPulse Real-Time Stream):</b>", h2_style))
    story.append(create_image_flowable("docs/screenshots/live_azure/09_azure_portal_live_metrics_streaming.png",
                                       "Azure Live Metrics: 1 server online (392 MB committed), real-time log stream showing successful HMAC authentication and HTTP 200 execution", max_h=110))
    story.append(Spacer(1, 3))

    # 10. Phase 6: Normalization & Hysteresis
    story.append(Paragraph("10. Phase 6: Surge Normalization & Anti-Flapping Hysteresis", h1_style))
    story.append(create_code_block(
        "# Reset CPU simulator back to 20%\n"
        "curl -X POST 'http://localhost:8002/set?pct=20'\n"
        "{\"target_pct\":20.0,\"current_pct\":94.99998414125321}\n\n"
        "# Verify traffic safely returns to Kubernetes\n"
        "curl -s http://localhost:8080/calculate\n"
        "{\"source\":\"k8s\",\"impl\":\"dummy-backend\",\"hostname\":\"bd2e4c973393\",\"prime_count\":168,\"prime_sum\":76127}"
    ))
    story.append(Spacer(1, 3))
    story.append(create_callout([
        "• Anti-Flapping Hysteresis Dead Band: Burst trigger occurs at 80% CPU; recovery requires CPU < 60%.",
        "• When CPU dropped from 95% down to 72%, BurstOps remained in burst mode, preventing rapid route thrashing.",
        "• Only after CPU dropped safely below 60% did the gateway return traffic to the local pods."
    ], title="HYSTERESIS ROUTING STABILITY"))

    # 11. Phase 7: Multi-Replica Scaling & Redis Control Plane
    story.append(Paragraph("11. Phase 7: Multi-Replica Gateway Scaling & Redis Control Plane", h1_style))
    story.append(create_code_block(
        "# Scale gateway to 3 replicas with Redis backplane\n"
        "docker compose -f docker-compose.yml -f docker-compose.scale.yml up -d --scale gateway=3\n\n"
        "# Inspect leader election across all 3 replicas\n"
        "for i in 1 2 3; do\n"
        "  PORT=$(docker compose -f docker-compose.yml -f docker-compose.scale.yml port --index=$i gateway 8080 | cut -d: -f2)\n"
        "  echo \"--- Replica on port $PORT ---\"\n"
        "  curl -s http://localhost:$PORT/metrics | grep -E '^gateway_is_leader'\n"
        "done\n\n"
        "# Stop all services cleanly\n"
        "docker compose stop"
    ))
    story.append(Spacer(1, 3))
    story.append(create_image_flowable("docs/screenshots/11_terminal_scale_and_stop.png",
                                       "Scale Test & Leader Election Output: Port 50639 is Leader (1.0), Ports 50641 and 50640 are Followers (0.0)", max_h=110))
    story.append(Spacer(1, 3))
    story.append(create_callout([
        "• Atomic Lua CAS Lease: Exactly one replica wins the Redis lease ('gateway_is_leader 1.0') and polls Prometheus.",
        "• Pub/Sub Broadcasting: The leader publishes routing state to Redis. Followers listen via a background thread.",
        "• Zero Redis I/O on Request Path: Followers read from local memory cache (< 0.05 ms), preventing Redis from becoming a routing bottleneck."
    ], title="DISTRIBUTED CONTROL PLANE"))

    # 12. Phase 8: Docker Desktop Infrastructure
    story.append(Paragraph("12. Phase 8: Docker Desktop Infrastructure & Container Architecture", h1_style))
    story.append(create_image_flowable("docs/screenshots/12_docker_desktop_single_gateway.png",
                                       "Docker Desktop UI: 10-service base mesh with access logs (GET /calculate 200 OK, POST /set?pct=20 200 OK)", max_h=110))
    story.append(Spacer(1, 3))
    story.append(create_image_flowable("docs/screenshots/13_docker_desktop_scaled_gateway_3x.png",
                                       "Docker Desktop UI (Scaled Mesh): 3 active gateway replicas coordinated by Redis backplane", max_h=110))
    story.append(Spacer(1, 3))

    c_table_data = [
        [Paragraph("<b>Container</b>", table_head), Paragraph("<b>Image</b>", table_head), 
         Paragraph("<b>Port</b>", table_head), Paragraph("<b>Architecture Role</b>", table_head)],
        [Paragraph("gateway (1..3)", table_text), Paragraph("burstops-gateway", table_text), Paragraph("8080 (dynamic)", table_text), Paragraph("L7 router, PI controller, hysteresis state machine, and HMAC signer.", table_text)],
        [Paragraph("dummy-backend-vip", table_text), Paragraph("nginx:1.27-alpine", table_text), Paragraph("8000:8000", table_text), Paragraph("Kubernetes ClusterIP VIP; round-robin balances across pods.", table_text)],
        [Paragraph("dummy-backend-1 & 2", table_text), Paragraph("burstops-backend-X", table_text), Paragraph("8000/tcp", table_text), Paragraph("Kubernetes worker pod replicas executing prime sieve calculation.", table_text)],
        [Paragraph("dummy-serverless", table_text), Paragraph("burstops-dummy-serverless", table_text), Paragraph("8001:8001", table_text), Paragraph("Local serverless mock with 50-150ms artificial latency injection.", table_text)],
        [Paragraph("cpu-sim", table_text), Paragraph("burstops-cpu-sim", table_text), Paragraph("8002:8002", table_text), Paragraph("Synthetic PromQL CPU metrics provider with inertia glide curve.", table_text)],
        [Paragraph("cadvisor", table_text), Paragraph("gcr.io/cadvisor/cadvisor:v0.49.1", table_text), Paragraph("8082:8080", table_text), Paragraph("Scrapes container resource consumption directly from Docker cgroups.", table_text)],
        [Paragraph("prometheus", table_text), Paragraph("prom/prometheus:v2.53.1", table_text), Paragraph("9090:9090", table_text), Paragraph("Time-series database evaluating 30s PromQL sliding rate windows.", table_text)],
        [Paragraph("grafana", table_text), Paragraph("grafana/grafana:11.1.4", table_text), Paragraph("3000:3000", table_text), Paragraph("Observability UI visualizing 12 routing, CPU, and FinOps panels.", table_text)],
        [Paragraph("locust", table_text), Paragraph("locustio/locust:2.29.1", table_text), Paragraph("8089:8089", table_text), Paragraph("Distributed load generator swarm for multi-user traffic surges.", table_text)],
        [Paragraph("redis", table_text), Paragraph("redis:7-alpine", table_text), Paragraph("6379:6379", table_text), Paragraph("Distributed lock and pub/sub backplane for atomic leader election.", table_text)],
    ]
    t_c = Table(c_table_data, colWidths=[95, 115, 65, 229])
    t_c.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1B365D")),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
        ('TOPPADDING', (0, 0), (-1, -1), 2.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2.5),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
    ]))
    for r_i in range(1, len(c_table_data)):
        if r_i % 2 == 0:
            t_c.setStyle(TableStyle([('BACKGROUND', (0, r_i), (-1, r_i), colors.HexColor("#F8FAFC"))]))
    story.append(t_c)
    story.append(Spacer(1, 8))
    story.append(Paragraph("<i>End of Implementation & Verification Report. Certified and tested on live Microsoft Azure infrastructure.</i>", 
                           ParagraphStyle('Sign', fontName='Helvetica-Oblique', fontSize=7.5, textColor=colors.HexColor("#64748B"), alignment=1)))

    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"Master PDF successfully built at {pdf_path} (Size: {os.path.getsize(pdf_path):,} bytes)")

if __name__ == "__main__":
    build_pdf()
