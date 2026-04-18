# Multi Agent Systems - Robot Mission

Project related to the Multiple Agents Systems lecture at CentraleSupelec. The purpose of the project is to implement a simple multi-agent system where multiple robots have to collaborate to achieve a common goal: to collect radioactive waste in a grid environment. The robots have to navigate the grid, collect the waste, transform it, then bring it to a specific location.

The project is implemented in Python using the Solara framework with Mesa.

## Setup

### Prerequisites

Make sure you have Python 3.10 or higher installed on your system. Then, you can install the required dependencies using pip:

```bash
pip install -r requirements.txt
```

### Running the model

To run the model, simply execute the following command from the repository ̀`1_robot_mission_MAS2026` directory:

```bash
solara run run.py
```

### Running the model with the comparisons of three different scenari

Three scenari: Random VS   Patrol+Memory and no communication   VS Patrol+Memory+Communication
To run the model, simply execute the following command from the repository ̀`group1_robot_mission_MAS2026` directory:

```bash
solara run run_comparison.py
```

## Model hypothesis

Most of the rules of the model are defined in the [subject file](./Self-organization%20of%20robots%20in%20a%20hostile%20environment%202026.pdf).

Nonetheless, we had to make some assumptions to implement the model. Here are the main ones:

- Two robots can't be on the same cell.
- Robot perception field is limited to the 4 adjacent cells (von Neumann neighborhood).
- Robots can only move in the 4 cardinal directions (no diagonal movement).
- Robots can communicate and do an action in the same step.

## Model design

Each of the three robot types are implemented in separate classes that all implement a common interface `Robot`. Here are the specificities of each robot type:

- **Green robots**: they are the only ones that can collect green waste that are randomly generated in the green area. They cannot exceed the green area. When they have 2 green waste in their inventory, they transform them into a yellow waste.
- **Yellow robots**: they are the only ones that can collect yellow waste produced by the green robots. They cannot go in the red area. When they have 2 yellow waste in their inventory, they transform them into a red waste.
- **Red robots**: they are the only ones that can collect red waste produced by the yellow robots. They can go everywhere but they are the only ones that can bring the waste to the disposal cell.

## Metrics

To evaluate the performance of our model, we defined several metrics:

|                    Notation                    | Metric                               | Description                                                                                                                                                                                                                                    |
| :--------------------------------------------: | ------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
|                     $C_f$                      | Final ratio of collected waste       | The ratio of collected waste to the total amount of waste generated. This metric gives us an idea of how efficient the robots are at collecting waste.                                                                                         |
|                      $T$                       | Scenario duration                    | Number of steps to conclude the scenario.                                                                                                                                                                                                      |
| $n_{k}(t)$ with $k \in \{green, yellow, red\}$ | Number of wastes collected over time | The number of wastes collected at each time step. This metric allows us to see how the collection process evolves over time and if there are any bottlenecks or periods of inactivity.                                                         |
|   $E_k$ with $k \in \{green, yellow, red\}$    | Exploration ratio                    | The ratio of time steps where robots are exploring (moving while searching for a waste) to the total number of time steps. This metric gives us insight into how much time the robots spend exploring the environment versus collecting waste. |
|   $ls_k$ with $k \in \{green, yellow, red\}$   | Average lifespan of wastes           | The average number of time steps that a waste remains in the environment before being fully processed (collected and transformed). This metric helps us understand how quickly the waste is being processed by the robots.      


## Communication procedure

what kind of message ? which method ? when do they communicate ?

## Authors

- [Alexandre Faure](mailto:alexandre.faure@student-cs.fr): student at CentraleSupelec
- [Sarah Lamik](mailto:sarah.lamik@student-cs.fr): student at CentraleSupelec
- [Ylias Larbi](mailto:ylias.larbi@student-cs.fr): student at CentraleSupelec
