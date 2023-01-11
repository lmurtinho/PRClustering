import numpy as np
from tqdm import tqdm
from sklearn.metrics.pairwise import euclidean_distances

def euclid_dist(x, y):
  return np.linalg.norm(x-y)

class PRClustering():

  def __init__(self, n_clusters, alpha=0.25, 
               n_init = 'square',
               dist_func=euclid_dist,
               use_min_dist = True,
               use_centroids = False,
               random_state=None):
    self.n_clusters = n_clusters
    self.d_cluster = bool(n_clusters % 2)
    self.alpha = alpha
    self.dist_func = dist_func
    self.rng = np.random.default_rng(seed=random_state)
    self.n_init = n_init
    self.use_min_dist = use_min_dist
    self.use_centroids = use_centroids
  
  def find_first_point(self, X):
    n = len(X)
    if self.n_init == 'square':
        test_n = int(np.floor(np.sqrt(n)))
    elif self.n_init == 'all':
        test_n = n
    elif type(self.n_init) == int:
        test_n = min(self.n_init, n)
    elif type(self.n_init) == float:
        test_n = min(int(np.floor(self.n_init * n)), n)
    else:
        test_n = 1
    to_test = self.rng.choice(n, test_n, replace=False)
    dists = euclidean_distances(X[to_test])
    idx_a, idx_b = dists.argmax() % test_n, dists.argmax() // test_n
    a, b = to_test[idx_a], to_test[idx_b]
    dists = euclidean_distances(X[[a, b]], X)
    best = dists.argmax() % test_n
    self.dists_to_centers = euclidean_distances(X[best].reshape(1, -1), X)
    self.dists_to_centers[:,best] = 0
    return best
  
  def find_distant_neighbor(self, X, u=None, i=None):
    if not self.u_centers:
      dists_to_center = self.dists_to_centers#.argmax()
    else:
      dists_to_center = self.dists_to_centers.sum(axis=0)
      if u is not None:
        factor = self.n_clusters - 2*i + 2
        ed = (euclidean_distances(X[u].reshape(1, -1), X) * factor).flatten()
        ed[self.u_centers + self.v_centers + [u]] = 0
        dists_to_center += ed
    best = dists_to_center.argmax()
    dists = euclidean_distances(X[best].reshape(1, -1), X)
    self.dists_to_centers = np.concatenate((self.dists_to_centers, dists))
    self.dists_to_centers[:,best] = 0
    for i in self.u_centers + self.v_centers:
      self.dists_to_centers[:,i] = 0
    if u:
      self.dists_to_centers[:,u] = 0
    return best
  
  def fit(self, X, y=None):
    # two "centers" will be selected at each iteration
    
    self.u_centers = []
    self.v_centers = []

    k_ = self.n_clusters // 2
    for i in tqdm(range(k_)):
        if len(self.u_centers) == 0:
           u = self.find_first_point(X)
        else:
           u = self.find_distant_neighbor(X)
        v = self.find_distant_neighbor(X, u, i)
        self.u_centers.append(u)
        self.v_centers.append(v)
    assert len(self.u_centers) == k_
    assert len(self.v_centers) == k_
    assert len(np.unique(self.u_centers + self.v_centers)) == 2 * k_
    if self.use_centroids:
      self.centroids = np.zeros((self.n_clusters, X.shape[1]))
      self.n_per_cluster = np.zeros(self.n_clusters)
      for i in range(k_):
        u_pos = 2*i
        v_pos = u_pos + 1
        self.centroids[u_pos] = X[self.u_centers[i]]
        self.centroids[v_pos] = X[self.v_centers[i]]
        self.n_per_cluster[u_pos] = 1
        self.n_per_cluster[v_pos] = 1


  def predict(self, X):
    labels = []
    if self.d_cluster:
      centers = self.u_centers + self.v_centers
    else:
      centers = self.u_centers[:-1] + self.v_centers[:-1]
    dists_uv = euclidean_distances(X[centers])
    dists_uv *= self.alpha
    for i in tqdm(range(len(X))):
      if i in self.u_centers:
        labels.append(self.u_centers.index(i))
      elif i in self.v_centers:
        labels.append(self.v_centers.index(i) + len(self.u_centers))
      else:
        cluster = self.find_label(X, X[i], dists_uv)
        labels.append(cluster)
        if self.use_centroids:
          self.centroids[cluster] = \
            (self.centroids[cluster] * \
              self.n_per_cluster[cluster] + \
                X[i]) / \
            (self.n_per_cluster[cluster] + 1)
          self.n_per_cluster[cluster] += 1
    labels = np.array(labels, dtype=int)
    self.labels_ = labels
    return labels

  def find_label(self, X, x, dists_uv):
    min_dist = np.inf
    label = None
    n_u = len(self.u_centers)

    if not self.d_cluster:
      centers = self.u_centers[:-1] + self.v_centers[:-1]
      n_u -= 1
    else:
      centers = self.u_centers + self.v_centers

    dists_x = euclidean_distances(X[centers],
                                     x.reshape(1, -1)).flatten()
    idx = dists_x.argmin()
    min_dist = dists_x.min()
    dists_x -= min_dist
    one_min = np.isclose(dists_x, 0).sum()
    all_distant = np.all(dists_x >= dists_uv[idx])
    if one_min and all_distant:
      if idx < n_u:
        label = 2 * idx
      else:
        label = 2 * (idx % n_u) + 1
    else:
      label = 2 * n_u
      if not self.d_cluster:
        if self.use_centroids:
          dist_u = self.dist_func(x, self.centroids[n_u])
          dist_v = self.dist_func(x, self.centroids[n_u+1])
        else:
          dist_u = self.dist_func(x, X[self.u_centers[-1]])
          dist_v = self.dist_func(x, X[self.v_centers[-1]])
        if dist_v < dist_u:
          label += 1
    return label

  def assign_to_cluster(self, x, u, min_dist, i, label, is_v=False):
    """
    - Checks the distance between x and u.
    - If smaller than min_dist, assigns x to label associated with u.
    - Label will be 2*i if u is a u_center, 2*i+1 if u is a v_center.
    - If points are assigned to the closest centroids, updates min_dist.
      - If centroids are being used, min_dist updated to the distance between
        x and the centroid of the cluster.
    """
    dist_v = self.dist_func(x, u)
    if dist_v < min_dist:
      label = 2*i + (1 if is_v else 0)
      if self.use_min_dist:
        if self.use_centroids:
          min_dist = self.dist_func(x, self.centroids[label])
        else:
          min_dist = dist_v
    return label, min_dist

  def check_hyperplane(self, x, u, v):
    z = v - u
    x_ = x - u
    proj = abs(np.dot(x_, z) / np.dot(z, z))
    # print(f'proj: {proj:.2f}, alpha: {self.alpha:.2f}')
    return proj <= self.alpha

  def check_ball(self, x, u, dist_uv):
    dist_ux = self.dist_func(x, u)
    # print(f'dist_ux: {dist_ux:.2f}, dist_uv: {dist_uv:.2f}')
    return dist_ux <= dist_uv

  def fit_predict(self, X, y=None):
    self.fit(X)
    return self.predict(X)