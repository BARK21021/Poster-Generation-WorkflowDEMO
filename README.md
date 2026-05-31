This directory contains ComfyUI workflow files and custom node implementations for poster automation and text overlay functionality.

<img width="300" height="300" alt="image" src="https://github.com/user-attachments/assets/f6703170-a6b0-4b1f-8b4e-848a4282273e" />
<img width="300" height="300" alt="image" src="https://github.com/user-attachments/assets/97f97139-61df-4849-bfee-573de4ac139c" />
<img width="256" height="384" alt="image" src="https://github.com/user-attachments/assets/b855ba1a-d483-41d9-9738-8035d15170aa" />

> **Note**: These are demo/study copies for learning and reference purposes.

## Files Overview

### FL Text Overlay Node Implementations

Two versions of the FL TextOverlay node with different algorithms:

#### FL_TextOverlay_Basic.py (Basic Version)
- **Source**: `comfyui_fill-nodes/nodes/vfx/FL_TextOverlay.py`
- **Coordinate System**: Percentage-based positioning (0-100%)
- **Features**:
  - Simple text overlay with 9-point anchor system
  - Basic font color control (RGB)
  - Direct PIL anchor parameter support
  - ~140 lines of code
- **Use Case**: Quick and simple text overlay tasks

#### FL_TextOverlay_Enhanced.py (Enhanced Version)
- **Source**: `comfyui_fill-nodes/nodes/FL_TextOverlay.py`
- **Coordinate System**: Pixel-based positioning
- **Advanced Features**:
  - Text Stroke/Outline - Floating-point stroke width support
  - Gradient Text Colors - Horizontal, vertical, and diagonal gradients
  - Auto Text Wrapping - Intelligent line breaking
  - Adaptive Font Sizing - Automatic font scaling to fit canvas
  - Enhanced Boundary Checking - Multi-level safety margins
  - ~558 lines of code
- **Use Case**: Professional poster design with advanced typography

### Key Algorithm Differences

| Feature | Basic Version | Enhanced Version |
|---------|---------------|------------------|
| Positioning | Percentage (0-100%) | Pixel values |
| Text Rendering | Single color + anchor | Single color / stroke / gradient |
| Font Management | Fixed size | Auto-adaptive scaling |
| Text Processing | Raw display | Auto-wrapping |
| Complexity | O(n) linear rendering | O(n×m) multi-sampling + interpolation |

---

## Workflow Files

### Local_Knowledge_Enhanced_LLM_Poster_Automation_Framework.json
**Main Workflow File**
- Knowledge-enhanced LLM-based poster automation framework
- Node-based workflow for automated poster generation
- Integrates language models with visual design pipeline

### Local_Knowledge_Enhanced_LLM_Poster_Automation_Framework_Copy.json
**Backup Copy**
- Duplicate of the main workflow file for safekeeping

---

## Research Report: Poster Automation Framework

### System Architecture Overview

This report presents a **layered decoupled poster automation generation system** based on knowledge-enhanced language models and ComfyUI node-based workflows. The system adopts a three-layer architecture:

| Layer | Core Technology | Main Function |
|-------|-----------------|---------------|
| **Planning Layer** | Knowledge-enhanced LLM (Qwen3-4b) | Requirement parsing → Structured design parameters |
| **Execution Layer** | ComfyUI + SDXL + Custom Nodes | Automated poster background generation & text overlay |
| **Interaction Layer** | Vue.js + Node.js | Template selection, parameter input, result display |

### Core Workflow Pipeline (6 Steps)

The system implements an **"Input → Plan → Generate → Composite → Display"** pipeline:

#### Step 1: User Input
- Users input poster themes, promotional purposes, or natural language descriptions in the interaction system
- Select templates, styles, or additional parameters as needed

#### Step 2: Knowledge-Enhanced LLM Planning Module (Core Innovation)
**This is the key innovation of the framework:**

- **RAG (Retrieval-Augmented Generation)**:
  - Built a **structured design knowledge base** with 50 professional rules across 5 categories:
    - Style matching (15 rules)
    - Color coordination (12 rules)
    - Layout design (10 rules)
    - Font selection (8 rules)
    - Design prohibitions (5 rules)
  - Uses **keyword-matching weighted linear retrieval algorithm** (no vector database needed)
  - Each rule contains: ID, category, trigger keywords (3-8 Chinese keywords), rule content (<100 words), weight coefficient
  - Retrieves Top-3 most relevant design rules based on user input

  > ⚠️ **Important Implementation Note**: The workflow JSON files provided in this directory **do not include the pre-built knowledge base**. The RAG knowledge base must be **manually created and configured** by the user. However, implementing this is relatively straightforward:
  >
  > - **Knowledge Base Format**: Simple JSON structure with 50 rules (can start with fewer, e.g., 10-20 core rules)
  > - **Rule Structure**: Each rule only needs: `id`, `category`, `keywords[]`, `content` (string), `weight` (number)
  > - **Storage Location**: Place in `ComfyUI/custom_nodes/comfyui_llm_party/file/` directory as `.json`, `.txt`, or `.csv`
  > - **Retrieval Algorithm**: Lightweight linear keyword matching - no complex embedding models or vector databases required
  > - **Easy to Customize**: Users can add domain-specific rules based on their own design preferences and industry needs
  >
  > **Getting Started**: You can begin with a minimal set of 10-15 basic design rules covering common scenarios (tech style, graduation poster, commercial promotion, etc.) and gradually expand. The system will work even with a small initial rule set.

- **CoT (Chain-of-Thought) Reasoning**:
  - Injects retrieved design rules into LLM's system prompt as hard constraints
  - Forces model to follow a **4-step reasoning process**:
    1. **Requirement Analysis**: Identify core theme, style positioning, target audience, keywords
    2. **Layout Decision**: Choose composition type, determine title/subtitle placement areas
    3. **Color & Font Decision**: Determine RGB color values, font family, font sizes with justification
    4. **Image Prompt Generation**: Generate positive and negative prompts for SDXL

- **Structured Output**: Model outputs JSON format containing:
  ```json
  {
    "title": "Main Title",
    "subtitle": "Subtitle",
    "prompt_positive": "English prompts for SDXL...",
    "prompt_negative": "Negative constraints...",
    "text_position": {"title_x": 120, "title_y": 150, ...},
    "font_size": {"title": 72, "subtitle": 36},
    "font_color": {"title": [255,255,255], "subtitle": [220,240,255]},
    "font_family": {"title": "SourceHanSansCN-Bold", "subtitle": "..."}
  }
  ```

**Key Advantage**: Solves the problem that general LLMs lack professional design knowledge and output unstructured/unusable parameters.

#### Step 3: SDXL Background Image Generation
- Receives structured prompts from planning module
- Uses **Stable Diffusion XL (SDXL)** model for high-quality background generation
- Applies **positive/negative prompt constraints** to control visual style
- K-Sampler node handles iterative rendering
- **Goal**: Generate theme-consistent visual background (NOT final poster with text)

**Hardware Optimization for Low VRAM (4GB)**:
- Reduces image resolution
- Enables partial parameter quantization
- Can fallback to SD1.5 model if needed (lower quality but more stable on 4GB VRAM)

#### Step 4: YOLO-based Forbidden Zone Detection
- Uses **YOLOv8 SEG (Segmentation) model** to identify main subjects in generated image
- Converts subject regions into **text layout forbidden zones**
- Prevents text from obscuring important visual elements
- Outputs: Mask + XY coordinate ranges of forbidden areas

> ⚠️ **Practical Limitations & Manual Adjustment Required**:
>
> While YOLO-based subject detection provides automated forbidden zone generation, **the recognition accuracy is not always perfect in practice**. Users should be aware of the following limitations:
>
> - **Detection Inconsistencies**: YOLO may fail to identify certain subjects (especially abstract artistic elements, complex compositions, or unusual objects), resulting in incomplete or inaccurate forbidden zones
> - **Over/Under-segmentation**: The model might mark too large an area (over-conservative, limiting text placement options) or too small (insufficient protection of key elements)
> - **Style-dependent Performance**: Detection works better for photorealistic images but can struggle with highly stylized, surreal, or heavily processed artwork common in poster designs
> - **Edge Cases**: Overlapping objects, low contrast subjects, or similar background colors can confuse the segmentation algorithm
>
> **Recommended Workflow**:
> 1. **Initial Auto-detection**: Let YOLO generate the initial forbidden zone mask
> 2. **Visual Review**: Always preview the generated mask overlay on the image to check accuracy
> 3. **Manual Adjustment**: Use ComfyUI's visual editing tools or coordinate parameters to:
>    - Expand/shrink forbidden zones as needed
>    - Add manual exclusion areas for missed subjects
>    - Remove false positive zones that are unnecessarily blocking text placement
> 4. **Iterative Refinement**: If text still overlaps important elements, manually adjust `text_position` coordinates in the workflow parameters
>
> **Tip**: For critical production work, consider combining YOLO auto-detection with a manual review step. The system provides the coordinates, but human judgment is often needed for optimal results.

**Alternative Considered but Rejected**:
- Qwen3-VL-4b (multimodal LLM): Has vision capability but Base64 encoding increases token overhead significantly, causing latency and context length overflow errors
- Cloud API: High network dependency, privacy risks, deployment costs

**Final Choice**: Use only Qwen3-4b (text-only) for stability; rely on YOLO for visual understanding (with manual oversight)

#### Step 5: Custom Text Overlay Node (FL_TextOverlay)
- **Receives inputs**: Background image + text content + position coordinates + color/font/size parameters
- **Performs**:
  - Auto line-wrapping based on title length and area width
  - Boundary checking to prevent text overflow
  - Stroke/outline rendering for readability
  - Gradient color support (horizontal/vertical/diagonal)
  - Adaptive font sizing to fit canvas
- **Outputs**: Final composite poster image

**Why Not Generate Text Directly with SD?**
- SD/SDXL models have **poor Chinese text generation quality**
- Common issues: Character distortion, spelling errors, stroke structure collapse
- FLUX models improve text rendering but require high VRAM (>8GB), not suitable for local 4GB deployment
- **Solution**: Separate background generation from text rendering (decoupling strategy)

#### Step 6: Frontend Display & Management
- Visualizes final poster result in browser interface
- Supports:
  - Result preview (Lightbox mode)
  - One-click download
  - Template editing continuation
  - History record management (LocalStorage)

### Problems Solved by This Framework

#### ✅ **Problem 1: Unstructured Design Output from General LLMs**
- **Issue**: General LLMs output vague, non-executable descriptions without specific parameters
- **Solution**: RAG knowledge base + CoT structured reasoning forces quantified, actionable output
- **Impact**: Downstream modules can directly execute without manual parameter adjustment

#### ✅ **Problem 2: Poor Chinese Text Rendering in Diffusion Models**
- **Issue**: SD/SDXL generates distorted, illegible Chinese characters
- **Solution**: Decoupled architecture - generate background first, then overlay text using PIL-based custom node
- **Impact**: Ensures 100% accurate, readable Chinese text in final posters

#### ✅ **Problem 3: High Hardware Requirements**
- **Issue**: Most AI poster tools require 8GB+ VRAM or cloud API access
- **Solution**:
  - Uses lightweight Qwen3-4b model (runs on 4GB VRAM)
  - Linear RAG retrieval (no embedding model/vector DB needed)
  - Optimized SDXL inference with quantization
  - Fallback to SD1.5 when necessary
- **Impact**: Enables local deployment on consumer-grade GPUs (RTX 3050 Ti)

#### ✅ **Problem 4: Lack of Professional Design Knowledge**
- **Issue**: Generic AI tools ignore design principles (layout, typography, color theory)
- **Solution**: 50-rule structured knowledge base covering industry best practices
- **Impact**: Generated posters follow professional design standards automatically

#### ✅ **Problem 5: Text-Subject Occlusion**
- **Issue**: Overlaid text may cover important visual elements in generated images
- **Solution**: YOLO-based subject detection creates forbidden zones for intelligent layout avoidance
- **Impact**: Maintains visual hierarchy and readability

#### ✅ **Problem 6: Privacy & Data Security Concerns**
- **Issue**: Cloud-based solutions risk data leakage
- **Solution**: Fully local execution - all data stored locally, no cloud transmission
- **Impact**: Suitable for sensitive applications (academic research, internal corporate use)

#### ✅ **Problem 7: Long Production Cycle & High Cost**
- **Issue**: Traditional manual poster design is slow and expensive
- **Solution**: End-to-end automation from natural language to final poster in seconds
- **Impact**: Reduces design time from hours/days to minutes; lowers cost to near-zero

### Technical Stack Summary

| Component | Technology | Version/Spec |
|-----------|------------|--------------|
| **LLM Engine** | Ollama + Qwen3-4b | 4B parameters, local inference |
| **Image Generation** | Stable Diffusion XL | High-detail background synthesis |
| **Subject Detection** | YOLOv8 SEG | Real-time segmentation |
| **Workflow Engine** | ComfyUI | Node-based visual programming |
| **Text Overlay** | Custom PIL Node | FL_TextOverlay (Basic/Enhanced) |
| **Frontend Framework** | Vue.js 3 + Pinia | Reactive SPA |
| **Backend Server** | Node.js | API proxy + WebSocket |
| **Target Hardware** | NVIDIA RTX 3050 Ti | 4GB VRAM |

### Key Innovations

1. **RAG + CoT Fusion Mechanism**: Combines retrieval-augmented generation with chain-of-thought reasoning for structured design decisions
2. **Linear Keyword Retrieval Algorithm**: Lightweight alternative to vector databases, suitable for low-resource environments
3. **Decoupled Text Rendering Strategy**: Separates image generation from text overlay to ensure Chinese character accuracy
4. **Forbidden Zone-Aware Layout**: YOLO-guided intelligent positioning prevents text-subject occlusion
5. **Local-First Architecture**: Zero cloud dependency, complete privacy preservation

---

*Report source: 22403020130_肖金鹏_.pdf (63 pages)*

## Technical Details

### Gradient Algorithm (Enhanced Version)
The enhanced version implements per-pixel/per-character color interpolation:
- Uses `_interpolate_color()` method for linear interpolation between start and end colors
- Supports three gradient modes: horizontal, vertical, and diagonal
- Sampling interval: 2 pixels for performance optimization

### Stroke Rendering Algorithm
- Circular range detection using distance calculation: `distance_squared = dx*dx + dy*dy`
- Supports floating-point stroke widths via integer boundary expansion
- Two-pass rendering: stroke layer first, then fill layer

### Adaptive Font Sizing
- Iterative font reduction algorithm (5% decrement per iteration)
- Considers stroke margin in boundary calculations
- Fallback mechanism: defaults to PIL built-in font on failure

---

## Usage Notes

1. **Font Dependencies**:
   - Basic version uses local fonts from `ROOT_FONTS` directory
   - Enhanced version supports system fonts via `FL_USE_SYSTEM_FONTS` environment variable

2. **Compatibility**:
   - Requires PIL/Pillow library
   - Enhanced version requires matplotlib for system font parsing
   - Tested with ComfyUI custom node ecosystem

3. **Performance Considerations**:
   - Basic version: Faster execution, suitable for batch processing
   - Enhanced version: More computationally intensive due to multi-sampling

---

## Directory Structure

```
my display/
├── FL_TextOverlay_Basic.py                              # Basic text overlay implementation
├── FL_TextOverlay_Enhanced.py                           # Enhanced version with advanced features
├── Local_Knowledge_Enhanced_LLM_Poster_Automation_Framework.json    # Main workflow
├── Local_Knowledge_Enhanced_LLM_Poster_Automation_Framework_Copy.json # Backup workflow
├── 22403020130_肖金鹏_.pdf                               # Research report (63 pages)
└── README.md                                             # This documentation file
```

---

## Applications

- **Learning & Education**: Study different algorithm implementations for text overlay
- **Algorithm Comparison**: Compare basic vs. enhanced approaches side-by-side
- **Workflow Patterns**: Understand LLM integration with ComfyUI node systems
- **Experimentation**: Test and modify code in a safe environment
- **Reference Material**: Well-documented examples for custom node development

---

*Last updated: 2026-05-31*
