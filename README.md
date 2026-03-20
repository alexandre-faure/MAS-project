# MAS-project

Project related to the Multiple Agents Systems lecture at CentraleSupelec

## Run the model

To run the model, simply execute the following command from the repository "1_robot_mission_MAS2026" directory:

```bash
solara run run.py
```

## Model hypothesis

Here are the asumptions we are making for the model:

- 2 robots can't be on the same cell
- Robot perception field is limited to the 4 adjacent cells (von Neumann neighborhood)
- Robots can only move in the 4 cardinal directions (no diagonal movement)
- Robots can communicate and do an action in the same step
