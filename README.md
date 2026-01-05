# Endoscopic 3D Reconstruction for Surgical Visualization  
Capstone Design Project

## Overview

This project focuses on reconstructing accurate 3D geometry from standard 2D endoscopic video. In many minimally invasive procedures—particularly in head and neck oncology—surgeons must make spatially complex decisions using flat video feeds. Our goal is to recover depth, geometry, and spatial context from these videos in a way that is accurate, reproducible, and compatible with real operating room constraints.

The system is designed as a research and validation platform that allows us to evaluate reconstruction performance in controlled settings before extending toward physical phantoms and clinical data.

---

## Project Objectives

The primary objectives of this project are to:

- Convert monocular endoscopic video into a meaningful 3D reconstruction  
- Improve reconstruction quality through intelligent frame filtering  
- Achieve clinically relevant spatial accuracy and reproducibility  
- Maintain computational efficiency suitable for near–real-time workflows  
- Validate performance against known ground-truth geometry  

---

## System Pipeline

The reconstruction pipeline is modular and structured to allow independent testing and optimization of each stage.

### High-Level Pipeline

```
Endoscopic Video
        │
        ▼
Frame Pre-Processing
(blur, noise, glare rejection)
        │
        ▼
Camera Pose Estimation
(Structure-from-Motion)
        │
        ▼
Sparse 3D Reconstruction
        │
        ▼
Dense 3D Reconstruction
        │
        ▼
Validation & Visualization
```

---

## Frame Pre-Processing

Raw endoscopic video contains many frames that negatively impact reconstruction quality. These include frames affected by motion blur, defocus, specular highlights, occlusions from surgical instruments, and excessive noise.

Automated filtering removes frames that fall below defined quality thresholds, improving both reconstruction accuracy and computational efficiency.

---

## Camera Pose Estimation

Using the filtered frame set, camera motion through the scene is estimated using structure-from-motion techniques. This step recovers camera position, orientation, and sparse 3D feature points, which form the backbone of the reconstruction process.

---

## 3D Reconstruction

With estimated camera poses, the system generates a dense 3D representation of the scene geometry. This stage emphasizes surface consistency, artifact reduction, and geometric fidelity.

---

## Validation Methodology

Reconstructed geometry is compared against known reference models to quantify spatial accuracy, reproducibility, and robustness to degraded input conditions such as noise or missing frames.

---

## Design Considerations

The system is developed to remain compatible with standard endoscopic hardware, minimize disruption to surgical workflow, and support scalable experimentation across datasets.

---

## Current Status

The current implementation supports automated frame filtering, camera pose estimation, dense reconstruction, and quantitative validation against reference models. Future work will focus on robustness improvements and extension to physical and clinical datasets.
