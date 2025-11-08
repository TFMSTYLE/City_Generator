# City Generator

![city-thumb](https://github.com/user-attachments/assets/039e67a3-59b1-48df-95a3-4c48bbf22de6)

**Author:** The French Monkey (TFMSTYLE)  
**Version:** 1.0.0  

---

## Overview

The City Generator creates procedural cityscapes composed of randomized building blocks arranged according to various zoning and layout rules.  
It supports multiple urban profiles such as downtown cores, suburbs, and industrial areas, generating either a single combined mesh or collections of individual building instances.  
The addon uses zoning profiles to define the character, density, and form of each generated city layout.

---

## Parameters

### Live Update
When enabled, the city automatically regenerates whenever parameters change.  
Useful for real-time tuning, but may reduce performance with large city grids.

---

### Zoning Type
Defines the general architectural and spatial pattern of the city layout.  
Each zoning type has different building heights, densities, and layouts.

Options include:  
- **Downtown** – Dense, tall skyscrapers in a grid.  
- **Commercial** – Mid-rise buildings in an offset grid.  
- **Mixed Use** – Blended building types with hexagonal street layouts.  
- **Residential** – Low-rise buildings with organic placement.  
- **Industrial** – Large, irregular structures for warehouse zones.  
- **Suburban** – Curved street layout with low density.  
- **Office Park** – Radial design with central clustering.

---

### Grid Size
Defines the overall size of the city grid in number of blocks.  
Larger values increase both city area and building count.

---

### Block Size
Sets the size of each block in scene units.  
Affects spacing and overall city scale.

---

### Road Width
Specifies the width of roads separating blocks.  
Higher values create wider streets and larger block gaps.

---

### Center Height Falloff
Controls how much building height decreases from the city center to the edges.  
Larger values create taller cores and smoother height transitions.

---

### Height Variation
Adjusts the amount of random variation applied to building heights.  
Higher values result in a more irregular skyline.

---

### Building Density
Multiplies the density of buildings within each block.  
Higher values fill more of each block with buildings.

---

### Building Gap
Sets the space between individual buildings inside a block.  
Increasing this value creates more open areas.

---

### Building Tilt
Applies small random rotational offsets to buildings for a less uniform appearance.  
Useful for organic or stylized layouts.

---

### Custom Buildings
Specifies a Blender collection containing custom building meshes.  
If set, these models will be used as instances instead of generated cubes.

---

### Seed
Controls the overall randomization of the city layout.  
Changing the seed results in a new city with the same parameters.

---

### Building Seed
A separate random seed that affects only building placement and selection when using custom models.  
Useful for keeping city layout consistent while varying building appearance.

---

### Inner Radius
Defines a circular area at the center where no buildings will be generated.  
Useful for plazas, lakes, or central landmarks.

---

### Custom Buildings (Toggle)
When enabled, displays the custom building collection settings.  
Allows easy switching between procedural and custom building modes.

---

## Operators

### Generate City
Generates or regenerates the city based on the current settings.  
If a master city object already exists, it will be rebuilt in place.

---

### Delete City
Removes the master city object and all its associated building instances.  
Also cleans up unused meshes created by the generator.

---

### Reset Settings
Restores all adjustable parameters to their default values.  
Does not affect the live update state or custom building collection link.

---

## Usage Notes

- Larger grid sizes and densities create more complex scenes and require more processing time.  
- The zoning type determines both the street pattern and building proportions.  
- Height variation and center falloff together control the overall skyline profile.  
- Custom buildings collections can contain multiple meshes; each will be randomly distributed.  
- For best performance with large layouts, disable **Live Update** while adjusting parameters.
