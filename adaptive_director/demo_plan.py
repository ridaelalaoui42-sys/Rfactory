"""Quick topic-to-style planning from the terminal."""
import argparse,json
from .router import choose_style,plan
def main():
    a=argparse.ArgumentParser()
    a.add_argument('--topic',default='New developer tool')
    a.add_argument('--style',choices=['bang','vox','huashu','drawing','stickman'])
    ns=a.parse_args()
    d=choose_style(ns.topic,override=ns.style)
    spec=plan(ns.topic,[{'start':0,'end':4,'focus':'hook','module':d['module']},{'start':4,'end':8,'focus':'mechanism','module':d['module']}])
    print(json.dumps({'selection':d,'example':spec},indent=2))
if __name__=='__main__':main()
