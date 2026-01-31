# Feature Landscape: AWS EC2 GPU Integration

**Domain:** Cloud GPU Worker Management (AWS EC2)
**Researched:** 2026-01-31
**Confidence:** MEDIUM

## Feature Landscape

### Table Stakes (Users Expect These)

Features users assume exist. Missing these = product feels incomplete.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| **Instance Creation/Deletion** | Core functionality from DO implementation; users expect parity | LOW | Pattern exists in DO provider; straightforward EC2 API integration |
| **SSH Key Management** | Required for secure worker access; standard practice | LOW | Can reuse DO pattern; AWS supports same key-based auth |
| **Region Selection** | AWS has 30+ regions; users need control over data locality and latency | LOW | Required for AWS (not needed for DO's simpler model); critical for compliance |
| **Instance Type Selection** | AWS has diverse GPU families (G4, G5, P3, P4, P5); users need flexibility | MEDIUM | Must support NVIDIA GPU instances; exclude non-GPU initially |
| **OS Image/AMI Selection** | AWS requires AMI selection vs DO's simpler "OS Image" concept | MEDIUM | Need pre-validated GPU-enabled AMIs (NVIDIA drivers, CUDA, container toolkit) |
| **Wait for Instance Start** | Pattern from DO; required for worker provisioning workflow | LOW | EC2 instance states differ from DO droplets; handle pending/running/stopped |
| **Wait for Public IP Assignment** | Pattern from DO; workers need connectivity | LOW | AWS assigns public IP at launch or via Elastic IP |
| **Security Group Configuration** | AWS networking requires explicit firewall rules | MEDIUM | Required for worker-server communication; can use default or custom SG |
| **VPC/Subnet Selection** | AWS requires network context (vs DO's simpler networking) | MEDIUM | Default VPC acceptable for MVP; custom VPCs for advanced users |
| **Volume Attachment** | Pattern from DO; model storage needs | MEDIUM | EBS volumes vs DO volumes; different attachment model |
| **Worker Pool Management** | Core GPUStack concept; scaling groups of identical workers | LOW | Pattern exists; apply to AWS instance groups |
| **Cloud Credentials (AWS Access Key/Secret)** | AWS authentication model | LOW | Similar to DO token pattern; standard AWS IAM |

### Differentiators (Competitive Advantage)

Features that set the product apart. Not required, but valued.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **Spot Instance Support** | 60-90% cost savings; major differentiator for AI workloads | HIGH | Requires interruption handling, checkpoint awareness, capacity monitoring |
| **Instance Family Flexibility** | Auto-select from G4/G5/P3/P4/P5 based on model requirements | MEDIUM | Attribute-based selection similar to AWS best practices; reduces user decision burden |
| **Availability Zone Awareness** | Cross-AZ deployment for resilience; AWS-specific optimization | MEDIUM | Critical for high availability; Spot best practice |
| **AMI Optimization with Pre-installed Stack** | Faster boot times; better UX than generic AMIs | MEDIUM | Custom AMI with GPUStack worker pre-installed vs cloud-init bootstrap |
| **Instance Reservation/On-Demand Hybrid** | Mix reserved capacity for baseline + on-demand for peaks | HIGH | Cost optimization for production workloads |
| **Auto-scaling Based on Queue Depth** | Scale workers based on model deployment queue | HIGH | Integration with GPUStack scheduler; not just metric-based |
| **Instance Health Checks & Auto-recovery** | Replace failed workers automatically | MEDIUM | AWS auto-recovery vs manual replacement in DO |
| **Cost Estimation & Budget Alerts** | Show estimated costs before creating; alert on spend | MEDIUM | AWS pricing API integration; per-instance cost tracking |
| **Placement Groups for Multi-GPU** | Cluster placement for distributed inference low-latency | MEDIUM | Required for H100/H200 multi-node distributed training |
| **Elastic Fabric Adapter (EFA) Support** | High-performance networking for distributed inference | HIGH | Required for P4d/P5 multi-node; complex setup |
| **Graviton + GPU (G5g) Support** | ARM-based GPU instances; cost optimization | MEDIUM | Different architecture; validate compatibility |
| **Outposts/Wavelength Support** | Edge deployment scenarios | HIGH | Enterprise feature; low priority for initial release |

### Anti-Features (Things to Deliberately NOT Build)

Features that seem good but create problems in this domain.

| Anti-Feature | Why Requested | Why Problematic | Alternative |
|--------------|---------------|-----------------|-------------|
| **Support for All 700+ EC2 Instance Types** | "Flexibility" | Cognitive overload; most aren't relevant for GPU inference | Focus on GPU-accelerated instances only (G4, G5, P3, P4, P5 families) |
| **Bare Metal (Trn1/Inf2) Instance Support** | "Support all AWS silicon" | Different architecture (AWS Inferentia/Trainium); requires different drivers, backends | Stick to NVIDIA GPU instances for initial release; add Trainium later if needed |
| **Full EC2 Instance Lifecycle Management** | "Complete control" | Scope creep; GPUStack manages workers, not arbitrary EC2 instances | Workers are cattle, not pets; create/delete only, no stop/start management |
| **Custom AMI Builder Integration** | "Complete flexibility" | Complex AMI management; security burden | Curate pre-tested AMIs; document manual AMI creation for advanced users |
| **Multi-Region Load Balancing** | "High availability" | GPUStack scheduler handles placement; premature optimization | Single-region clusters initially; document multi-region as architecture pattern |
| **AWS Batch/ECS/EKS Integration** | "Use managed services" | Different abstraction level; would compete with GPUStack's Kubernetes support | Keep direct EC2 control; point users to separate Kubernetes provider for EKS |
| **Automatic Savings Plans/Reserved Instance Purchasing** | "Cost optimization" | Financial commitment complexity; outside GPUStack's scope | Document cost optimization strategies; leave purchasing decisions to users |
| **Windows GPU Instance Support** | "OS choice" | Different driver model, container runtime; adds complexity | Linux only (Ubuntu/Debian) aligned with GPUStack's current stack |
| **On-Premises Outposts Support** | "Hybrid cloud" | Complex hardware requirements; not MVP | Cloud-only AWS for initial release |
| **Detailed CloudWatch Integration** | "Observability" | CloudWatch is complex; GPUStack has its own observability | Use GPUStack's built-in metrics; simple CloudWatch agent optional |

## Feature Dependencies

```
[AWS Credentials]
    └──requires──> [Region Selection]
                        └──requires──> [VPC/Subnet Selection]
                                            └──requires──> [Security Group Configuration]
                                                                └──requires──> [Instance Creation]
                                                                                    ├──requires──> [AMI Selection]
                                                                                    ├──requires──> [Instance Type Selection]
                                                                                    ├──requires──> [SSH Key Management]
                                                                                    ├──requires──> [Wait for Instance Start]
                                                                                    └──requires──> [Wait for Public IP]

[Spot Instance Support]
    └──requires──> [Instance Family Flexibility] (fallback types)
    └──requires──> [Availability Zone Awareness] (capacity pools)
    └──enhances──> [Cost Estimation] (spot vs on-demand pricing)

[Volume Attachment]
    └──requires──> [Instance Creation] (must be in same AZ)
    └──enhances──> [Worker Pool Management] (shared storage)

[Placement Groups]
    └──requires──> [Multi-AZ Awareness] (placement within AZ)
    └──conflicts──> [Spot Instances] (Spot doesn't support placement groups)

[Auto-scaling]
    └──requires──> [Worker Pool Management]
    └──requires──> [Instance Health Checks]
    └──requires──> [GPUStack Scheduler Integration] (queue depth metrics)
```

### Dependency Notes

- **Instance Creation requires Region → VPC → Subnet → Security Group chain:** AWS networking is hierarchical; these must be selected in order.
- **Spot Instances require fallback types:** To get Spot capacity, must be flexible across multiple instance types and AZs.
- **Placement Groups conflict with Spot:** Spot instances cannot be placed in placement groups; users must choose one.
- **Volumes must be in same AZ as instance:** EBS volumes are AZ-specific; this constraint affects worker pool design.

## MVP Definition

### Launch With (v1)

Minimum viable product — what's needed to validate AWS EC2 GPU integration.

- [ ] **AWS Credentials (Access Key/Secret)** — Required for all AWS API calls
- [ ] **Region Selection** — Core AWS concept; must support before instance operations
- [ ] **VPC/Subnet Selection** — Required for instance creation; default VPC acceptable
- [ ] **Security Group Configuration** — Required for worker-server communication
- [ ] **SSH Key Management** — Pattern from DO; required for worker access
- [ ] **Instance Creation/Deletion** — Core functionality; parity with DO
- [ ] **Instance Type Selection (G4dn, G5, P3, P4de, P5)** — Core GPU families for inference
- [ ] **AMI Selection (pre-validated list)** — Deep Learning AMI or Ubuntu with NVIDIA drivers
- [ ] **Wait for Instance Start + Public IP** — Pattern from DO; required for provisioning flow
- [ ] **Worker Pool Management** — Core GPUStack abstraction; apply to AWS
- [ ] **Volume Attachment (EBS)** — Pattern from DO; model storage requirement

### Add After Validation (v1.x)

Features to add once core is working.

- [ ] **Spot Instance Support** — Trigger: Users request cost optimization
- [ ] **Instance Family Flexibility** — Trigger: Users need automatic instance type selection
- [ ] **Availability Zone Awareness** — Trigger: Spot instances require multi-AZ strategy
- [ ] **AMI Optimization (custom GPUStack AMI)** — Trigger: Slow boot times with cloud-init
- [ ] **Instance Health Checks** — Trigger: Users report worker failures not being detected
- [ ] **Cost Estimation** — Trigger: Users need visibility into AWS spend

### Future Consideration (v2+)

Features to defer until product-market fit is established.

- [ ] **Auto-scaling Based on Queue Depth** — Why defer: Requires scheduler integration; complex
- [ ] **Placement Groups for Multi-GPU** — Why defer: Requires distributed inference validation
- [ ] **Elastic Fabric Adapter (EFA) Support** — Why defer: Complex networking; P4d/P5 only
- [ ] **Reserved Instance/On-Demand Hybrid** — Why defer: Financial complexity; user can manage
- [ ] **G5g (ARM GPU) Support** — Why defer: Architecture validation required
- [ ] **Outposts/Wavelength** — Why defer: Edge use cases; different deployment model

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| AWS Credentials | HIGH | LOW | P1 |
| Region Selection | HIGH | LOW | P1 |
| VPC/Subnet Selection | HIGH | MEDIUM | P1 |
| Security Group Configuration | HIGH | MEDIUM | P1 |
| SSH Key Management | HIGH | LOW | P1 |
| Instance Creation/Deletion | HIGH | LOW | P1 |
| Instance Type Selection | HIGH | MEDIUM | P1 |
| AMI Selection | HIGH | MEDIUM | P1 |
| Wait for Start/Public IP | HIGH | LOW | P1 |
| Worker Pool Management | HIGH | LOW | P1 |
| Volume Attachment | MEDIUM | MEDIUM | P1 |
| Spot Instance Support | HIGH | HIGH | P2 |
| Instance Family Flexibility | MEDIUM | MEDIUM | P2 |
| AZ Awareness | MEDIUM | MEDIUM | P2 |
| AMI Optimization | MEDIUM | MEDIUM | P2 |
| Health Checks | MEDIUM | MEDIUM | P2 |
| Cost Estimation | MEDIUM | MEDIUM | P2 |
| Auto-scaling | MEDIUM | HIGH | P3 |
| Placement Groups | LOW | MEDIUM | P3 |
| EFA Support | LOW | HIGH | P3 |

**Priority key:**
- P1: Must have for launch
- P2: Should have, add when possible
- P3: Nice to have, future consideration

## Competitor/Comparable Feature Analysis

| Feature | DigitalOcean (Current) | AWS (Target) | RunPod | CoreWeave | Our Approach |
|---------|------------------------|--------------|--------|-----------|--------------|
| Instance Types | Limited (NVIDIA GPU Droplets) | Extensive (G4-P5 families) | Extensive (consumer to H100) | Extensive (bare metal) | Start with G4/G5/P3/P4/P5 NVIDIA |
| Spot/Preemptible | No | Yes (Spot) | Yes (Secure Cloud) | Yes (interruption handling) | P2: Add Spot support |
| Region Options | 10+ regions | 30+ regions | 10+ regions | 3 regions | Support all AWS regions |
| Network Complexity | Simple | VPC/Subnet/SG required | Simple | Simple | Abstract with sensible defaults |
| Cost Optimization | Basic | Complex (Spot, RI, Savings) | Simple pricing | Simple pricing | P2: Spot support; P3: RI guidance |
| Auto-scaling | Manual | Manual (EAS groups separate) | Yes (serverless) | Yes | P3: Queue-based auto-scaling |
| Worker Bootstrap | Cloud-init | Cloud-init/AMI | Custom | Custom | Cloud-init first; P2: Custom AMI |
| Multi-AZ | No | Yes | Limited | Yes | P2: AZ awareness |

## AWS-Specific Considerations

### Instance Family Recommendations

| Family | GPUs | VRAM | Use Case | Priority |
|--------|------|------|----------|----------|
| **G4dn** | 1x T4 | 16GB | Inference, dev/test | P1 |
| **G5** | 1x A10G | 24GB | Inference, graphics | P1 |
| **P3** | 1-8x V100 | 16-128GB | Training, inference | P1 |
| **P4de** | 8x A100 | 320GB | Large model training | P2 |
| **P5** | 8x H100 | 640GB | Frontier training | P3 |
| **G5g** | 1x T4G | 16GB | ARM-based inference | P3 |
| **Inf2/Trn1** | AWS Silicon | N/A | AWS-specific | Exclude (v1) |

### AMI Strategy

| Approach | Pros | Cons | Recommendation |
|----------|------|------|----------------|
| **Deep Learning AMI (AWS)** | Pre-installed drivers, CUDA, toolkit | Large, slow boot, may have extra packages | Recommended for P1 |
| **Ubuntu + cloud-init bootstrap** | Fresh install, controlled | Slower boot, requires network | Fallback option |
| **Custom GPUStack AMI** | Fastest boot, pre-configured | Maintenance burden, security updates | P2 optimization |
| **Marketplace AMIs** | Specialized configurations | Licensing complexity, trust | Not recommended |

### Networking Defaults

| Setting | Default | Rationale |
|---------|---------|-----------|
| VPC | Default VPC | Simplifies setup; works in all regions |
| Subnet | First available in VPC | Sensible default; user can override |
| Security Group | Create new with required ports | Ensures GPUStack communication works |
| Public IP | Assign at launch | Workers need to reach GPUStack server |
| Placement | Default (spread) | Good default; placement groups P3 |

## Sources

- GPUStack DigitalOcean Documentation: https://docs.gpustack.ai/2.0/tutorials/adding-gpucluster-using-digitalocean/
- GPUStack Cluster Management: https://docs.gpustack.ai/latest/user-guide/cluster-management/
- AWS EC2 GPU Instance Types: https://aws.amazon.com/ec2/instance-types/p4/, https://aws.amazon.com/ec2/instance-types/g5/
- AWS Spot Best Practices: https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/spot-best-practices.html
- AWS GPU Instance Guide (nOps): https://www.nops.io/blog/amazon-ec2-gpu-instances-the-complete-guide/
- AWS GPU Best Practices (Sedai): https://sedai.io/blog/aws-gpu-instances-best-practices-tips
- Cloud GPU Platform Comparison (DigitalOcean): https://www.digitalocean.com/resources/articles/best-cloud-gpu-platforms
- AWS Cost Optimization Blog: https://aws.amazon.com/blogs/aws-cloud-financial-management/navigating-gpu-challenges-cost-optimizing-ai-workloads-on-aws/

---
*Feature research for: AWS EC2 GPU Integration (GPUStack)*
*Researched: 2026-01-31*
