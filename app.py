import json

from flask import Flask, render_template, request

app = Flask(__name__)

@app.route('/', methods=['GET', 'POST'])
def main():
    return render_template('index.html')

@app.route('/graph', methods=['GET'])
def graph():
    graph_data = {
          "nodes": [
            {
              "id": "n0",
              "label": "A node",
              "x": 0,
              "y": 0,
              "size": 3
            },
            {
              "id": "n1",
              "label": "Another node",
              "x": 3,
              "y": 1,
              "size": 2
            },
          ],
          "edges": [
            {
              "id": "e0",
              "source": "n0",
              "target": "n1"
            },
          ]
        }
    return render_template('graph.html', json_data=json.dumps(graph_data))


if __name__ == '__main__':
  app.run(debug= True,host="127.0.0.1",port=5000, threaded=True)