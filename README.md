# Code Segment
The code has been structured similarly to the assignments in class. The base folder is *LabelPropagation* and needs to be placed inside the folder with a student tag just like in the assignments, e.g. dk7405. The entire project can be run using the GradingSoftware shared during our assignments. The next section mentions the steps for executing the project.

Folder path - $HOME/A8/dk7405/LabelPropagation/...

## Execution Steps
 ### 1. Execution of preliminary test cases.
 - Extract the zip folder and put it inside a folder named **A8**.
 - The individual datasets should be present inside a parent folder.
 - Inside the zip folder the config file will be present marked *grading_a8_q1.json*. Put it in some other location and copy the absolute path to it.
 - Fill in the absolute paths to the data parent folder, the query file, and the neo4j connection in the config file.
 - Once the above steps are done, open a command prompt and follow the below steps for the grading software.
 - The program will create files in the LabelPropagation/ folder to log the outputs.
   
 ### 2. Execution of Community Analysis with ground truth
 - Running this evaluation takes a considerable amount of time and memory (For Amazon, time: 5+ hrs and memory: 512mb-1 GB).
 - For running this evaluation, increase the memory limit on grading software and specify these additional parameters in the config file test cases,
 	- gt_file: These files are given. Keep it in the parent folder and use the absolute path to the ground truth communities file.
	- similarity: Which coefficient to use among 'Jaccard', 'Sorensen', and 'Overlap'
	- penalty: whether to penalize or not (true/false)
  	- Example: "{\"database\":\"com-youtube\", \"repetitions\":100, \"tolerance\":0, \"gt_file\": \"/Users/devroopkar/Documents/RIT/Fall 2024/CSCI 723/GroundTruths/com-youtube/com-youtube.all.cmty.txt\", \"similarity\": \"Jaccard\", \"penalty\": false}"
- Follow the last 2 steps in Execution 1. and check the log outputs to see the results.
   	

## Grading Software
To install: 
PYTHON_DIR/venv/bin/poetry install

To run:
PYTHON_DIR/venv/bin/poetry run python ./gradingsoftware/edu/rit/gdb/grading/GradingSoftware.py PYTHON_DIR/venv/bin/ ASSIGNMENT_FOLDER CONFIG_FOLDER/grading_ax_qx.json


Instructions:

- It receives three command-line parameters:
	1) The 'bin' folder of the Python environment to use.

	2) The assignment folder where the student solutions are located, e.g., '$HOME/A1/'. If crrvcs is a student, the program will process '$HOME/A1/crrvcs/'.

	3) The grading configuration folder where the JSON files are located.
