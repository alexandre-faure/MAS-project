# Multi Agent Systems - Robot Mission

Project related to the Multiple Agents Systems lecture at CentraleSupelec. The purpose of the project is to implement a simple multi-agent system where multiple robots have to collaborate to achieve a common goal: to collect radioactive waste in a grid environment. The robots have to navigate the grid, collect the waste, transform it, then bring it to a specific location.

The project is implemented in Python using the Solara framework with Mesa.

## 1. Setup

### 1.1. Prerequisites

Make sure you have Python 3.10 or higher installed on your system. Then, you can install the required dependencies using pip:

```bash
pip install -r requirements.txt
```

### 1.2. Running the model

To run the model, simply execute the following command from the repository ̀`1_robot_mission_MAS2026` directory:

```bash
solara run run.py
```

### 1.3. Running the model with the comparisons of three different scenari

Three scenari: Random VS Patrol+Memory and no communication VS Patrol+Memory+Communication
To run the model, simply execute the following command from the repository ̀`1_robot_mission_MAS2026` directory:

```bash
solara run run_comparison.py
```

## 2. Model hypothesis

Most of the rules of the model are defined in the [subject file](./Self-organization%20of%20robots%20in%20a%20hostile%20environment%202026.pdf).

Nonetheless, we had to make some assumptions to implement the model. Here are the main ones:

- Two robots can't be on the same cell.
- Robot perception field is limited to the 4 adjacent cells (von Neumann neighborhood).
- Robots can only move in the 4 cardinal directions (no diagonal movement).
- Robots can communicate and do an action in the same step.

## 3. Model design

### 3.1. Environment

The environment is represented as a grid of size $w$ x $h$ (width x height). Each cell of the grid is associated with a given radioactivity level between 0 and 1. The grid is divided into three areas based on the radioactivity level:

- **Green area** (west): cells with radioactivity level between 0 and 0.33. This area is the least radioactive.
- **Yellow area** (center): cells with radioactivity level between 0.33 and 0.67.
- **Red area** (east): cells with radioactivity level between 0.67 and 1. This area is the most radioactive.

![Map example](images/map.png)

Initially, a certain number of green waste are randomly generated in the green area. The waste are represented as objects that can be collected by the robots and transformed into other types of waste (see section 3.3).

### 3.2. Robots

On the map, three types of robots are present and share the same goal: to collect the waste and bring it to the disposal cell located in the red area. The robots have different capabilities and costs, which will be detailed in the next section.

Each of the three robot types are implemented in separate classes that all implement a common interface `Robot`. Here are the specificities of each robot type:

- **Green robots**: they are the only ones that can collect green waste that are randomly generated in the green area. They cannot exceed the green area. When they have 2 green waste in their inventory, they transform them into a yellow waste.
- **Yellow robots**: they are the only ones that can collect yellow waste produced by the green robots. They cannot go in the red area. When they have 2 yellow waste in their inventory, they transform them into a red waste.
- **Red robots**: they are the only ones that can collect red waste produced by the yellow robots. They can go everywhere but they are the only ones that can bring the waste to the disposal cell.

### 3.3. Waste

Wastes are inert objects that can be mered (for green and yellow waste) or collected by the robots. They are represented as objects that have a type (green, yellow or red) and a position on the grid. Green wastes are initially generated in the green area and can be transformed by the robots as follows:

```mermaid
flowchart TD
    A[Green Waste] --> E[Yellow Waste]
    B[Green Waste] --> E
    C[Green Waste] --> F[Yellow Waste]
    D[Green Waste] --> F
    E --> G[Red Waste]
    F --> G
```

## 4. Metrics

To measure and objectively compare the performance of the model under different scenarios, we will define several metrics. For synthetic purpose, we denote $\mathcal C = \{green, yellow, red\}$ the set of waste types and robot types.

### 4.1. Completion metrics

$T$: the scenario duration (number of steps to conclude the scenario).

$C_f$: the final ratio of collected waste.

$$C_f = \frac{N_{collected}}{1,75 \cdot N_{generated}^{green}}$$

Where $N_{collected}$ is the total number of waste collected by the robots and $N_{generated}^{green}$ is the total number of waste generated in the environment. A higher final ratio indicates that more waste has been collected, which is a sign of better performance. We multiply by $1,75$ because 4 gree wastes are transformed into 2 yellow wastes, then 1 red waste.

### 4.2. Speed metrics

$ls_k$ with $k \in \mathcal C$: the average lifespan of wastes. This metric gives us an idea of how quickly the waste is being processed by the robots. A lower average lifespan indicates that the waste is being processed and transformed more efficiently.

$$ls_k = \frac{1}{N_k} \sum_{i=1}^{N_k} (t_{processed}^i - t_{generated}^i)$$

Where $N_k$ is the number of wastes of type $k$ that were processed, $t_{processed}^i$ is the time step at which waste $i$ was processed (collected and transformed or landed on the disposal area), and $t_{generated}^i$ is the time step at which waste $i$ was generated.

$expl_k$ with $k \in \mathcal C$: the exploration ratio. This metric gives us insight into how much time the robots spend exploring the environment versus collecting waste. A higher exploration ratio may indicate that the robots are spending more time searching for waste, while a lower ratio may suggest that they are more efficient at finding and collecting waste.

$$expl_k = \frac{T_{exploration}}{T_k}$$

Where $T_{exploration}$ is the total time spent by robots of type $k$ exploring the environment, and $T_k$ is the duration until which all wastes of type $k$ and below are collected.

### 4.3. Load balancing metrics

$load_k$ with $k \in \mathcal C$: the load balancing ratio. This metric gives us an idea of how well the workload is distributed among the robots.

$$load_k = \frac{1}{N_k} \sum_{i=1}^{N_k} \frac{w_i}{\sum_{j=1}^{N_k} w_j}$$

Where $N_k$ is the number of robots of type $k$ and $w_i$ is the amount of waste collected by robot $i$. A load balancing ratio close to 1 indicates that the workload is evenly distributed among the robots, while a ratio close to 0 indicates that one or a few robots are doing most of the work.

## 5. Model evaluation

### 5.1. Settings

We freeze some of the settings of the model:

- Grid size ($w$ x $h$): 18 x 14
- Number of green wastes: 20
- Max number of steps: 400

Based on the problem, we will consider that each robot has a given cost per step. This is justified because the higher the radioactivity of the area, the more the robot will be expensive to maintain and operate. We will consider the following costs for each type of robot:

- Green robots: 1 unit of cost per step
- Yellow robots: 2 units of cost per step
- Red robots: 3 units of cost per step

### 5.2. Scenarios

#### 5.1.1. Main scenarios

We will consider 3 main scenarios with different robots behaviors:

- **Scenario 1 ($S^{rand}$)**: Random behavior: robots move randomly in the environment and collect waste whenever they find it.
- **Scenario 2 ($S^{k}$)**: Knowledge based behavior: robots have a basic knowledge of the environment and try to move towards the areas where they are more likely to find waste.
- **Scenario 3 ($S^{com}$)**: Communication based behavior: robots communicate with each other to share information about the location of waste and coordinate their movements to optimize the collection process.

#### 5.1.2. Sub-scenarios

In addition, we will further specify scenarios in different sub-scenarios with different numbers of robots of each type to evaluate the impact of the cost on the overall performance of the system:

- **Sub-scenario $n_g, n_y, n_r$ ($S_{n_g, n_y, n_r}$)**: Random behavior with $n_g$ green robots, $n_y$ yellow robots and $n_r$ red robots.

We will study those sub-scenarios: $S_{1, 1, 1}$, $S_{1, 2, 3}$, $S_{3, 2, 1}$, $S_{3, 3, 3}$, $S_{5, 5, 5}$.

## 6. Results

For each scenario and each scenario, we will run 10 simulations and compute the average of the metrics defined in section 4 with respect to the cost of the robots. We will then compare the results of the different scenarios to evaluate the impact of the different behaviors and the cost on the overall performance of the system.

## Authors

- [Alexandre Faure](mailto:alexandre.faure@student-cs.fr): student at CentraleSupelec
- [Sarah Lamik](mailto:sarah.lamik@student-cs.fr): student at CentraleSupelec
- [Ylias Larbi](mailto:ylias.larbi@student-cs.fr): student at CentraleSupelec
