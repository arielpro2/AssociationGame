import json
import os
from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask, render_template, request
from flask_sqlalchemy import SQLAlchemy
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_caching import Cache
from flask_socketio import SocketIO


app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = f'postgresql://{os.environ["POSTGRES_USER"]}:{os.environ["POSTGRES_PASS"]}@{os.environ["POSTGRES_HOST"]}:{os.environ["POSTGRES_PORT"]}/db'
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config['CACHE_TYPE'] = 'SimpleCache'
app.config['CACHE_DEFAULT_TIMEOUT'] = 0
app.secret_key = os.environ["FLASK_SECRETKEY"]

scheduler = BackgroundScheduler()
cache = Cache(app)
limiter = Limiter(app, key_func=get_remote_address)
socketio = SocketIO(app)

db = SQLAlchemy(app)


class nodesTable(db.Model):
    key = db.Column(db.Integer, primary_key=True)
    id = db.Column(db.Integer, unique=True)
    label = db.Column(db.String(), unique=True, nullable=False)
    def __init__(self,id, label):
        self.id = id
        self.label = label


class edgesTable(db.Model):
    key = db.Column(db.Integer, primary_key=True)
    id = db.Column(db.Integer, unique=True)
    from_id = db.Column(db.Integer, nullable=False)
    to_id = db.Column(db.Integer, nullable=False)
    votes = db.Column(db.Integer, nullable=False)
    def __init__(self,id, from_id, to_id, votes):
        self.id = id
        self.from_id = from_id
        self.to_id = to_id
        self.votes = votes

def validate_label(label):
    if len(label.split(' ')) > 1:
        return False
    if not label[0].isupper() or not label[1:].islower():
        return False
    return True

def getNetworkFromSql():
    nodes_query = nodesTable.query.filter_by().all()
    edges_query = edgesTable.query.filter_by().all()
    nodes = {str(node.id): {'id':str(node.id),'label':str(node.label)} for node in nodes_query}
    label2id = {str(node.label): str(node.id) for node in nodes_query}
    edges = {f'{min(edge.from_id,edge.to_id)}-{max(edge.from_id,edge.to_id)}': {'id':str(edge.id),'label':str(edge.votes), 'from':str(edge.from_id), 'to':str(edge.to_id)} for edge in edges_query}
    return {'nodes':nodes,'edges':edges, 'label2id':label2id}

def updateSqlFromCache():
    cache_node_list = list(cache.get('nodes').values())
    cache_edge_list = list(cache.get('edges').values())
    query_nodes = [nodesTable(node['id'], node['label']) for node in cache_node_list]
    query_edges = [edgesTable(edge['id'], edge['from'], edge['to'], edge['label']) for edge in cache_edge_list]
    with app.app_context():
        nodesTable.query.delete()
        edgesTable.query.delete()
        db.session.bulk_save_objects(query_nodes)
        db.session.bulk_save_objects(query_edges)
        db.session.commit()
    print('Network Saved to DB')



#startup
@app.before_first_request
def initializeCache():
    network = getNetworkFromSql()
    cache.set('nodeCount', len(network['nodes']))
    cache.set('edgeCount', len(network['edges']))
    cache.set('nodes', network['nodes'])
    cache.set('edges', network['edges'])
    cache.set('label2id', network['label2id'])
    scheduler.add_job(func=updateSqlFromCache, trigger="interval", seconds=60)
    scheduler.start()

#Pages
@app.route('/', methods=['GET', 'POST'])
def Main():
    return render_template('index.html')

@app.route('/graph', methods=['GET'])
def Graph():
    nodes = cache.get('nodes')
    edges = cache.get('edges')
    return render_template('graph.html', nodes=list(nodes.values()), edges=list(edges.values()))

#API
@app.route('/api/getNetwork', methods=['GET'])
def getNetwork():
    return json.dumps(getNetworkFromSql())

#@limiter.limit("10/minute")
@app.route('/api/addNode', methods=['POST'])
def addNode():
    label = request.form["label"]
    from_id = request.form["from_id"]

    temp_nodes = cache.get('nodes')
    temp_label2id = cache.get('label2id')
    temp_edges = cache.get('edges')

    if from_id not in temp_nodes:
        return 'From id doesnt exist'

    from_label = temp_nodes[from_id]['label']
    if label == from_label:
        return 'Labels cant be the same'

    if not validate_label(label) or not validate_label(from_label):
        return 'Incorrect label format'

    user_cache = cache.get(request.remote_addr)
    #if user_cache:
    #    if {'from_label': from_label, 'label': label} in user_cache or {'from_label': label, 'label':from_label } in user_cache:
    #        return 'Already Requested'

    #Node handling
    if label not in temp_label2id:
        to_id = cache.get('nodeCount')
        temp_nodes[str(to_id)] = {'id': str(to_id), 'label':label}
        socketio.emit('newNode', temp_nodes[str(to_id)])
        cache.set('nodeCount', to_id+1)
        cache.set('nodes', temp_nodes)
        temp_label2id[label] = str(to_id)
        cache.set('label2id', temp_label2id)
    else:
        to_id = cache.get('label2id')[label]

    #Edge handling
    if f'{min(int(from_id),int(to_id))}-{max(int(from_id),int(to_id))}' in temp_edges:
        #Edge exists, incrementing votes
        temp_edge = temp_edges[f'{min(int(from_id),int(to_id))}-{max(int(from_id),int(to_id))}']
        temp_edge['label'] = str(int(temp_edge['label'])+1)
        temp_edges[f'{min(from_id,to_id)}-{max(from_id,to_id)}'] = temp_edge
        socketio.emit('updateEdge', temp_edge)
        cache.set('edges', temp_edges)
    else:
        #New edge
        edge_id = cache.get('edgeCount')
        temp_edges[f'{min(int(from_id),int(to_id))}-{max(int(from_id),int(to_id))}'] = {'id': edge_id, 'from': from_id, 'to':to_id, 'label':'1'}
        socketio.emit('newEdge', temp_edges[f'{min(int(from_id),int(to_id))}-{max(int(from_id),int(to_id))}'])
        cache.set('edgeCount', edge_id + 1)
        cache.set('edges', temp_edges)

    if cache.get(request.remote_addr):
        request_list = cache.get(request.remote_addr)
        request_list.append({'from_label':from_label, 'label':label})
        cache.set(request.remote_addr, request_list)
    else:
        cache.set(request.remote_addr, [{'from_label':from_label, 'label':label}])

    return 'Success'


if __name__ == '__main__':
    socketio.run(app, debug=os.environ['DEBUG'] == 'True', ssl_context='adhoc')


