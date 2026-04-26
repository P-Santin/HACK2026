# BAYMAXXING: Optimizing Storage Solutions 

## Contents:
* [Introduction to the project](#what-is-baymaxxing)
* [Repository contents](#repository-contents)
* [Use Overview](#use-overview)
* [Requirements](#requirements)
* [Installation](#installation)

## What is BAYMAXXING?

BAYMAXXING is a complex features an advanced heuristic optimizer designed to solve 2D Bin Packing problems with 3D spatial constraints. It leverages computational geometry and parallel processing to generate high-density warehouse racking layouts.

#### 1. Data Structures & Geometric Modeling:

The script utilizes Python `@dataclass` structures to represent warehouse elements and store their geometrical references, such as vertices' position, body dimensions and costs. The layout's trigonometric methods allow to precisely calculate the coordinates and relative location of the bodies in the warehouse based on their rotation and position.


#### 2. The Objective Function (Success Metric): 

The score function evaluates solution quality, returning a value the algorithm seeks to minimize. The underlying mathematics are:

$$Q = max \left( \frac{\sum BayPrice}{\sum BayLoad}, 1 \right)^{2.0 - Used Area}$$

Minimizing the above prioritizes bays with the lowest cost-to-capacity ratio. The Used Area is a ratio ($0$ to $1$). If the warehouse is 100% full, the exponent is $1$. If it is nearly empty, the exponent approaches $2$, severely penalizing the economic base. This forces the algorithm to maximize density.

As a safety measure, we decided to write the base of the function as the maximum between the ratio of TotalCost and TotalLoad and 1, in case that fraction's value fell below 1, which would cause the algorithm to minimize the Used Area parameter.

#### 3. Geometric Engine (Shapely):

Collision validation is delegated to the Shapely library. Within the `worker_aggressive_packer`, all geometry is converted into polygons. Together with the Floating Point Tolerance (buffer(-1.0)) technique, the algorithm virtually shrinks polygons by 1mm before checking for collisions. This mathematical "trick" allows two bays to touch exactly at their edges (sharing coordinates) without triggering a false positive for overlapping by the validation function.

#### 4. Core Heuristic: Active Node Packing:

This is the most complex component. Instead of scanning the warehouse coordinate-by-coordinate, it uses a Priority Queue `heapq` to propagate organically, similar to crystallization. The queue is seeded with warehouse corners, obstacle boundaries, and a coarse 2-meter grid. Each point in the queue has a priority, and depending on the direction_mode parameter, (e.g., 'BL' for Bottom-Left), the algorithm pulls points from the bottom-left first, creating a directional construction flow using a directional gravity method.

Upon selecting a valid coordinate, the algorithm always attempts to fit the most economically efficient bay type (bays_sorted) first. Then, it tests a 180° rotation on the bay’s axis. If it detects that this rotation aligns its aisle (gap) with an existing aisle, it locks that rotation. This forces the creation of shared logistical arteries, which results in a decrease of occupied space. The algorithm verifies that the bay stays within boundaries, avoids obstacles, respects varying ceiling heights, and does not overlap with other structural footprints. Once a bay is successfully placed, the coordinates of its 8 vertices (4 footprint, 4 gap) are injected back into the priority queue. This ensures the next bay is attempted immediately adjacent to the current one. 
 
#### 5. Parallelization
Since the search space is infinite and the expexted time limit is of 30 seconds, run_parallel_optimization spawns the heuristic across all available CPU cores (mp.cpu_count()). Each parallel worker receives a different "gravity" directive ('BL', 'TR', 'LB', etc.).This allows the script to simultaneously explore packing patterns from all four corners and the center outwards. An internal timer aborts execution at 27 seconds to ensure the process gracefully returns the best-found distribution before the hard limit.
 
#### 6. Export & Visualization

The winning solution is packaged into WorldProxy, exported to solution.csv, and rendered via Matplotlib. In the 2D map, bay footprints are opaque while aisles are semi-transparent; this allows for a visual audit where overlapping aisles (representing maximum efficiency) appear as darker, intensified colors.

## Repository contents

The structure of this repository contains the core optimization engine, the necessary input files, and the output directories:

```text
📦 baymaxxing
 ┣ 📜 optimizer.py          # Core heuristic and parallel processing engine
 ┣ 📜 environment.py        # Visualizer engine
 ┣ 📦 TestCases             # Folder with test cases
 |  ┣ 📜 warehouse.csv         # Input: Warehouse perimeter coordinates
 |  ┣ 📜 obstacles.csv         # Input: Internal obstacles and restricted areas
 |  ┣ 📜 ceiling.csv           # Input: Stepped ceiling heights
 |  ┗ 📜 types_of_bays.csv     # Input: Catalog of available bay types
 ┣ 📜 solution.csv          # Output: Final bay placements (Generated)
 ┣ 📜 solution.png          # Output: 2D Render of the layout (Generated)
 ┗ 📜 README.md             # Project documentation
 ``` 


## Requirements
% comparar con varias ejecuciones para decidir 

matplotlib, spdf, pandas, streamlit, plotly, shapely, 
