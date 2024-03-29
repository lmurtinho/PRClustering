from pr_clustering import PRClustering
import get_scores as gs
import valohai
import os
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.cluster import AgglomerativeClustering
import json
import joblib

# Load the data

VH_INPUTS_DIR = os.getenv('VH_INPUTS_DIR', '.inputs')
data_path = f'{VH_INPUTS_DIR}/data'
algos = json.loads(valohai.parameters('algos').value)
print(algos)

dataset = valohai.parameters('dataset').value
if dataset == 'all':
    datasets = [i.split('_')[0] for i in os.listdir(data_path)]
else:
    datasets = json.loads(dataset)
print(datasets)

alpha = valohai.parameters('alpha').value
n_init = valohai.parameters('n_init').value
avoid_small_clusters = valohai.parameters('avoid_small_clusters').value

if n_init.isdigit():
    n_init = int(n_init)
else:
    try:
        n_init = float(n_init)
    except:
        pass

seeds = range(1, 11)

def retrieve_labels(data, function, dataset, type, model_args, seeds=None):
    models = []
    ans = []
    seeds = [0] if seeds is None else seeds
    for seed in seeds:
        model = retrieve_model(function, seed, model_args)
        ans.append(model.fit_predict(data))
        model_ans = {'model': model,
                        'dataset': dataset,
                        'seed': seed,
                        'type': type}
        for key, val in model_args.items():
            model_ans[key] = val
        models.append(model_ans)
    models_path = valohai.outputs('models').path(f'{dataset}_{type}_models.pkl')
    joblib.dump(models, models_path)
    return ans

def retrieve_model(function, seed, model_args):
    if seed:
        return function(**model_args, 
                        random_state=seed)
    else:
        return function(**model_args)

def save_labels(df, name):
    labels_path = valohai.outputs('labels').path(name)
    df.to_csv(labels_path, index=False)

for dataset in datasets:
    print(dataset)
    filename = [i for i in os.listdir(data_path) 
                if i.startswith(dataset + '_')][0]
    data, k = gs.get_data(data_path, filename)
    args = {'n_clusters': k}
    if 'sl' in algos:
        args['linkage'] = 'single'
        labels = retrieve_labels(data, AgglomerativeClustering, dataset, 'sl', args)
        df_labels = pd.DataFrame(labels).T
        name = f'{dataset}_sl.csv'
        save_labels(df_labels, name)
        del args['linkage']
    if 'km' in algos:
        labels = retrieve_labels(data, KMeans, dataset, 'km', args, seeds)
        df_labels = pd.DataFrame(labels).T
        df_labels.columns = range(1,11)
        name = f'{dataset}_km.csv'
        save_labels(df_labels, name)
    if 'pr' in algos:
        args['alpha'] = alpha
        args['n_init'] = n_init
        args['avoid_small_clusters'] = avoid_small_clusters
        labels = retrieve_labels(data, PRClustering, dataset, 'pr', args, seeds)
        df_labels = pd.DataFrame(labels).T
        df_labels.columns = range(1,11)
        name = f'{dataset}_{alpha}.csv'
        save_labels(df_labels, name)
