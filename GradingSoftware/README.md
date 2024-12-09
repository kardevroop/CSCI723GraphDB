To install:

PYTHON_DIR/venv/bin/poetry install

To run:

PYTHON_DIR/venv/bin/poetry run python ./gradingsoftware/edu/rit/gdb/grading/GradingSoftware.py PYTHON_DIR/venv/bin/ ASSIGNMENT_FOLDER CONFIG_FOLDER/grading_ax_qx.json


Instructions:

- It receives three command-line parameters:
	1) The 'bin' folder of the Python environment to use.

	2) The assignment folder where the student solutions are located, e.g., '$HOME/A1/'. If crrvcs is a student, the program will process '$HOME/A1/crrvcs/'.

	3) The grading configuration folder where the JSON files are located.

