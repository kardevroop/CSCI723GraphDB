import decimal
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from threading import Timer

import psutil
import toml
import neo4j
from neo4j import GraphDatabase


def main():
    # This is where the bin folder is located in your machine. This is because you want to create a venv. You must have
    #   Poetry installed in this virtual environment.
    python_exec = sys.argv[1]
    # The folder you need to point to. This folder should contain several folders, one for each student's solution.
    assignment_folder = sys.argv[2]
    # The JSON file to be executed, in other words, the configuration for the question.
    json_config_file = sys.argv[3]

    # This is the output that I need for assigning grades.
    json_output = {}

    # TODO Change this if you want to print your output
    print_output = False

    # TODO Change this if you just want to print your retrieved data.
    print_retrieved = False

    # Let's parse the JSON file and start with the fun!
    with open(json_config_file, encoding='utf-8') as f:
        json_config = json.load(f)
        # Get all values starting with $ and replace them by other values in the document.
        #   Dot notation can be used.
        replace_dollar_sign_values(json_config, json_config)

    if json_config is None:
        print('The grading software could not read the JSON file, '
              'this is not a good sign; I am exiting.')
        sys.exit(-1)

    question_name = json_config['name']
    print('Working on:', question_name)

    # Let's process each student folder.
    for student_folder in os.listdir(assignment_folder):
        print('Student:', student_folder)

        if student_folder.startswith('_'):
            continue

        # Add results to the output.
        json_to_report = {'question': question_name, 'reasons': []}
        json_output[student_folder] = json_to_report

        # Find the folder with the answer.
        def find_folder():
            for file in Path(os.path.join(
                    assignment_folder, student_folder)).rglob(question_name):
                if os.path.isdir(file):
                    return file

        folder_to_find = find_folder()

        if folder_to_find is None:
            json_to_report['verdict'] = False
            json_to_report['reasons'].append('No folder ('+question_name+') was found. I am done.')
            continue

        # Does it contain a 'pyproject.toml' file?
        toml_file = os.path.join(folder_to_find, 'pyproject.toml')
        if json_config.get('project_type', True) and not os.path.exists(toml_file):
            json_to_report['verdict'] = False
            json_to_report['reasons'].append('No \'pyproject.toml\' file was found. I am done.')
            continue

        # Get the total size and make sure it is within the requirements. By default, 2048.
        # https://stackoverflow.com/questions/1392413/calculating-a-directorys-size-using-python
        folder_size = sum(f.stat().st_size
                          for f in folder_to_find.glob('**/*') if f.is_file())/1024
        if folder_size > json_config.get('maxFolderSize', 2048):
            json_to_report['verdict'] = False
            json_to_report['reasons'].append(
                'The total size of the folder is ' + str(folder_size) +
                ', which is larger than expected. Please, reduce the size, '
                'it should only contain source code.')
            continue

        if json_config.get('project_type', True):
            # Let's change to the Poetry project folder, so we can run commands from there.
            os.chdir(folder_to_find)
            try:
                # Let's build this thing! Nothing to remove... I think!
                p = psutil.Popen([python_exec + 'poetry', 'lock'],
                                 stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
                stdout, stderr = p.communicate(timeout=5 * 60)

                p = psutil.Popen([python_exec + 'poetry', 'install'],
                                 stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
                stdout, stderr = p.communicate(timeout=5*60)

                # There is no way to know whether the previous command worked... I mean,
                #   there may be, but it implies parsing the output and stuff... ugh!
                #   Let's be happy and assume they worked! :-)
            except Exception as oops:
                print('A major problem happened:', oops)
                json_to_report['verdict'] = False
                json_to_report['reasons'].append(
                    'Could not compile/install the Poetry project. Please, fix whatever issue '
                    'you are having (see above).')

                if psutil.pid_exists(p.pid):
                    p.kill()
                    json_to_report['reasons'].append(stdout)

                continue

        # This gets a new Neo4j driver and session from the JSON config file.
        def get_neo4j_connection(db_name):
            if 'database_neo4j' not in json_config:
                raise Exception('Neo4j database was not provided in the JSON file.')

            neo4j_cfg = json_config['database_neo4j']

            # Since Neo4j community edition does not support multiple schemas, we are forced
            #   to come up with all these stuff. Thanks a lot, Neo4j!
            # This is expecting Neo4jEmbeddedMultiple is running.
            if 'folder' in neo4j_cfg:
                # If ./SNA is the Neo4j folder, this will access ./SNA/{db_name}/
                with open(os.path.join(neo4j_cfg['folder'], db_name + '.swap'), 'w') as fw:
                    fw.write('\n')

                # It takes a little bit. Add more secs if needed!
                time.sleep(15.0)

            return GraphDatabase.driver(neo4j_cfg['url'], database='neo4j')

        # If we need to create files before running your program.
        if 'before_files' in json_config:
            for to_create in json_config['before_files']:
                if 'file' in to_create:
                    # This is a file.
                    with open(to_create['file'], 'w') as fw:
                        if 'contents' in to_create:
                            for line in to_create['contents']:
                                fw.write(str(line) + '\n')

        if 'before_neo4j_queries' in json_config:
            for to_run in json_config['before_neo4j_queries']:
                query, db_name = to_run, None

                # It can be a database and a query (dict)!
                if isinstance(to_run, dict):
                    query = to_run['query']
                    db_name = to_run['database']

                driver = get_neo4j_connection(db_name)
                session = driver.session()
                session.run(query)
                session.close()
                driver.close()

        if json_config.get('project_type', True):
            # Load .toml configuration.
            toml_config = toml.load(toml_file)
            # Find the entry point.
            entry_point = toml_config['tool']['poetry']['scripts']['entry-point']

            # Let's run the entry point using the parameters specified in the JSON config.
            path_to_script = entry_point.split(':')[0].split('.')
            path_to_script[len(path_to_script)-1] += '.py'
            to_run = [python_exec + 'poetry', 'run', 'python', os.path.join(*path_to_script)]
            for command in json_config['input_command_line']:
                to_run.append(command['value'])

            def print_process_output(output_to_print):
                if print_output and output_to_print is not None:
                    print('Process output:')
                    for i, line in enumerate(output_to_print.splitlines()):
                        print('\t', line)

            try:
                start = time.time()

                # Let's change to the current folder and run the command.
                os.chdir(folder_to_find)
                p = psutil.Popen(to_run, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

                # Check memory usage every couple of seconds. By default, 64MB and every two seconds.
                timer = RepeatTimer(json_config.get('pythonMemCheck', 2), check_memory_usage,
                                    args=(p, json_config.get('maxMemory', 64), json_to_report))
                timer.start()

                # We will wait a little bit; 1min by default. Wait... wait... wait...
                stdout, stderr = p.communicate(timeout=json_config.get('maxTimeMin', 1) * 60)

                # Kill them all!
                kill_recursive(p, timer)

                end = time.time()
                time_taken = (end - start)/3600
                json_to_report['reasons'].append('The process took ' + str(time_taken) + ' hours.')

                print_process_output(stdout)
            except subprocess.TimeoutExpired as oops:
                json_to_report['verdict'] = False
                json_to_report['reasons'].append('The process did not run in the expected time.')
                print_process_output(oops.stdout)
            except Exception as oops:
                json_to_report['verdict'] = False
                json_to_report['reasons'].append('A major problem happened when running the program!')
                json_to_report['reasons'].append(str(oops))
            finally:
                # Kill them all!
                kill_recursive(p, timer)

        def check_retrieved_expected():
            if time_taken is not None:
                json_to_report['reasons'].append(
                    'Test case: ' + str(i + 1) + ' took ' + str(time_taken) + ' seconds.')

            if print_retrieved:
                print('Test case: ' + str(i + 1))

                for j in range(0, len(retrieved)):
                    print(json.dumps(retrieved[j]))

                print('\n')
                return

            if len(retrieved) != len(expected):
                json_to_report['verdict'] = False
                json_to_report['reasons'].append(
                    'Test case: ' + str(i + 1) + '; Retrieved size: ' + str(len(
                        retrieved)) + '; Expected size: ' + str(len(expected)) + '.')

            for j in range(0, min(len(retrieved), len(expected))):
                if retrieved[j] != expected[j]:
                    json_to_report['verdict'] = False
                    json_to_report['reasons'].append(
                        'Test case: ' + str(i + 1) + '; Retrieved ' + str(j + 1) +
                        ' not as expected; Retrieved: ' + str(retrieved[j]) +
                        '; Expected: ' + str(expected[j]) + '.')

        # Let's run the test cases!
        for i, tc in enumerate(json_config['test_cases']):
            try:
                # Let's check the type.
                # This is a Cypher query that will return a result. The order is important!
                if tc.get('type', '') == 'Neo4jResultSet':
                    if 'query' in tc:
                        cypher_query = tc['query']
                    elif 'file' in tc:
                        # Read query from file provided.
                        with open(os.path.join(folder_to_find, tc['file']), encoding='utf-8') as f:
                            cypher_query = f.read()

                    # Run query and retrieve results. Get expected results.
                    start = time.time()

                    retrieved = []

                    driver = get_neo4j_connection(tc.get('database'))
                    session = driver.session(default_access_mode=neo4j.READ_ACCESS)
                    tx = session.begin_transaction(timeout=json_config.get('maxTimeMin', 1) * 60)
                    result = tx.run(cypher_query)
                    for record in result:
                        retrieved.append(record.data())
                    tx.close()
                    session.close()
                    driver.close()

                    expected = tc['expected']

                    end = time.time()
                    time_taken = (end - start) / 60

                    # Check expected!
                    # Add time taken if we are running the query from a file.
                    if 'file' not in tc:
                        time_taken = None

                    check_retrieved_expected()

                # There is a file and we wish to read and compare all the lines.
                if tc.get('type', '') == 'ReadJSONLines':
                    expected = tc['expected']

                    retrieved = []
                    with open(tc['file'], 'r') as fr:
                        for retrieved_line in fr.read().splitlines():
                            retrieved.append(json.loads(retrieved_line))

                    time_taken = None
                    check_retrieved_expected()

                # There is a file and we wish to read and compare the i-th line.
                if tc.get('type', '') == 'ReadLine':
                    selected_line, expected_line, line_no = None, tc['expected'], tc['line']

                    with open(tc['file'], 'r') as fr:
                        lines = fr.read().splitlines()
                        if line_no < len(lines):
                            selected_line = lines[line_no]

                    if print_retrieved:
                        print('Test case:', i, '--', selected_line)
                        continue

                    if selected_line is None or selected_line != expected_line:
                        json_to_report['verdict'] = False
                        json_to_report['reasons'].append(
                            'Test case: ' + str(i + 1) + '; Retrieved line: ' + selected_line +
                            '; Expected line: ' + expected_line + '.')

            except Exception as oops:
                json_to_report['verdict'] = False
                json_to_report['reasons'].append('A major problem happened when running the test cases!')
                json_to_report['reasons'].append(str(oops))

        if 'verdict' not in json_to_report:
            # Everything good! Congrats!
            json_to_report['verdict'] = True

    # Print the JSON document. We are done! Yay!
    print('JSON doc collected:')

    def decimal_default(obj):
        if isinstance(obj, decimal.Decimal):
            return float(obj)
        raise TypeError

    print(json.dumps(json_output, ensure_ascii=False, default=decimal_default).encode('utf8').decode())


# This method finds, recursively, string values that start with $ and replaces them by other
#   values in the document. Dot notation like "$x.y" is allowed.
# Replacing $ values in plain arrays is not supported!
def replace_dollar_sign_values(json_config_original, json_config_current):
    for key in json_config_current:
        if isinstance(json_config_current[key], str) and json_config_current[key].startswith('$'):
            path = json_config_current[key].replace('$', '').split('.')

            # Use path to get the other value.
            to_search = json_config_original
            other_value = None
            for idx, elem in enumerate(path):
                # Giving up if the element is not there.
                if elem not in to_search:
                    break
                # Last element.
                if idx == len(path) - 1:
                    other_value = to_search[elem]
                else:
                    # Update dictionary to search.
                    to_search = to_search[elem]

            # Replace value.
            if other_value is not None:
                json_config_current[key] = other_value
        elif isinstance(json_config_current[key], dict):
            replace_dollar_sign_values(json_config_original, json_config_current[key])
        # It is a list!
        elif isinstance(json_config_current[key], list):
            for elem in json_config_current[key]:
                if isinstance(elem, dict):
                    replace_dollar_sign_values(json_config_original, elem)


def kill_recursive(p, timer=None):
    # Done! Cancel the timer you fool!
    if timer is not None:
        timer.cancel()

    if p is None or not psutil.pid_exists(p.pid):
        return

    everybody = p.children(recursive=True)
    everybody.append(p)

    for proc in everybody:
        if psutil.pid_exists(proc.pid):
            proc.kill()

# Combining these answers:
# https://stackoverflow.com/questions/43775551/how-to-limit-memory-and-cpu-usage-in-python-under-windows
# https://stackoverflow.com/questions/12435211/threading-timer-repeat-function-every-n-seconds
class RepeatTimer(Timer):
    def run(self):
        while not self.finished.wait(self.interval):
            self.function(self, *self.args, **self.kwargs)

def check_memory_usage(timer, p, limit, json_to_report):
    if not psutil.pid_exists(p.pid):
        return

    # Let's check parent and all children!
    everybody = p.children(recursive=True)
    everybody.append(p)

    to_kill = False
    for proc in everybody:
        mem = proc.memory_info().rss/1e6
        if mem > limit:
            to_kill = True
            break

    if to_kill:
        # Kill them all!
        kill_recursive(p, timer)

        # Report issue.
        json_to_report['verdict'] = False
        json_to_report['reasons'].append('Process\'s memory usage:' + str(mem) +
                                         'MB exceeds memory limit (' + str(limit) + 'MB); the process will be killed.')


if __name__ == "__main__":
    main()
