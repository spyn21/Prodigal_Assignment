import sys, os
sys.path.insert(0, os.getcwd())
from evaluation.evaluate import run_evaluation
run_evaluation('evaluation/scenarios.json')
