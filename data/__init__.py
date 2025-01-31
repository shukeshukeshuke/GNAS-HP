import dgl
import torch
import torch.nn as nn
from data.molecules import MoleculeDataset,MoleculeDatasetDGL
from data.QM9 import QM9Dataset
from data.SBMs import SBMsDataset
from data.TSP import TSPDataset
from data.superpixels import SuperPixDataset
from data.cora import CoraDataset
from data.TUs import TUsDataset
from models.networks import *
from utils.utils import *

class FeatureConcatEncoder(nn.Module):
    """General Feature encoder with concatenation for different feature
    Args:
        feature_dims (list): a list of dim of input feature
        hidden_size (int): hidden dimension of embedding
    """

    def __init__(self, feature_dims, hidden_size, padding=False):
        super(FeatureConcatEncoder, self).__init__()

        self.embedding_list = nn.ModuleList()

        for i, dim in enumerate(feature_dims):
            if padding:
                emb = nn.Embedding(dim, hidden_size, padding_idx=0)
            else:
                emb = nn.Embedding(dim, hidden_size)
            self.embedding_list.append(emb)
        self.proj = nn.Linear(len(feature_dims) * hidden_size, hidden_size)

    def reset_parameters(self):
        for emb in self.embedding_list:
            emb.reset_parameters()
        self.proj.reset_parameters()

    def forward(self, x):
        x_embeddings = []
        for i in range(x.shape[-1]):
            x_embeddings.append(self.embedding_list[i](x[..., i]))
        x_embeddings = torch.cat(x_embeddings, dim=-1)
        return self.proj(x_embeddings)

class TransInput(nn.Module):

    def __init__(self, args, trans_fn):
        super().__init__()
        self.args = args
        self.trans = trans_fn
        self.K = args.K
        self.node_dim = args.node_dim

    def forward(self, input):
        if self.trans:
            input['V'] = self.trans(input['V'])
        return input


class TransOutput(nn.Module):

    def __init__(self, args):
        super().__init__()
        self.args = args
        if args.task == 'node_level': 
            channel_sequence = (args.node_dim, ) * args.nb_mlp_layer + (args.nb_classes, )
            self.trans = MLP(channel_sequence)
        elif args.task == 'link_level':
            channel_sequence = (args.node_dim * 2, ) * args.nb_mlp_layer + (args.nb_classes, )
            self.trans = MLP(channel_sequence)
        elif args.task == 'graph_level':
            channel_sequence = (args.node_dim, ) * args.nb_mlp_layer + (args.nb_classes, )
            self.trans = MLP(channel_sequence)
        else:
            raise Exception('Unknown task!')
            

    def forward(self, input):
        G, V = input['G'], input['V']
        if self.args.task == 'node_level':
            output = self.trans(V)
        elif self.args.task == 'link_level':
            def _edge_feat(edges):
                e = torch.cat([edges.src['V'], edges.dst['V']], dim=1)
                return {'e': e}
            G.ndata['V'] = V
            G.apply_edges(_edge_feat)
            output = self.trans(G.edata['e'])
        elif self.args.task == 'graph_level':
            G.ndata['V'] = V
            readout = dgl.mean_nodes(G, 'V')
            output = self.trans(readout)
        else:
            raise Exception('Unknown task!')
        return output


def get_trans_input(args):
    if args.data in ['ZINC']:
        trans_input = nn.Embedding(args.in_dim_V, args.node_dim) 
    elif args.data in ['TSP']:
        trans_input = nn.Linear(args.in_dim_V, args.node_dim)
    elif args.data in ['SBM_CLUSTER', 'SBM_PATTERN']:
        trans_input = nn.Embedding(args.in_dim_V, args.node_dim)
    elif args.data in ['CIFAR10', 'MNIST', 'Cora']:
        trans_input = nn.Linear(args.in_dim_V, args.node_dim)
    elif args.data in ['QM9']:
        trans_input = nn.Linear(args.in_dim_V, args.node_dim)
    elif args.data in ['ENZYMES', 'DD', 'PROTEINS_full']:
        trans_input = nn.Linear(args.in_dim_V, args.node_dim)
    else:
        raise Exception('Unknown dataset!')
    return trans_input


def get_loss_fn(args):
    if args.data in ['ZINC', 'QM9']:
        loss_fn = MoleculesCriterion()
    elif args.data in ['TSP']:
        loss_fn = TSPCriterion()
    elif args.data in ['SBM_CLUSTER', 'SBM_PATTERN']:
        loss_fn = SBMsCriterion(args.nb_classes)
    elif args.data in ['CIFAR10', 'MNIST']:
        loss_fn = SuperPixCriterion()
    elif args.data in ['Cora']:
        loss_fn = CiteCriterion()
    elif args.data in ['ENZYMES', 'DD', 'PROTEINS_full']:
        loss_fn = TUsCriterion()
    else:
        raise Exception('Unknown dataset!')
    return loss_fn


def load_data(args):
    if args.data in ['ZINC']:
        return MoleculeDataset(args.data)
    elif args.data in ['QM9']:
        return QM9Dataset(args.data, args.extra)
    elif args.data in ['TSP']:
        return TSPDataset(args.data)
    elif args.data in ['MNIST', 'CIFAR10']:
        return SuperPixDataset(args.data) 
    elif args.data in ['SBM_CLUSTER', 'SBM_PATTERN']: 
        return SBMsDataset(args.data)
    elif args.data in ['Cora']:
        return CoraDataset(args.data)
    elif args.data in ['ENZYMES', 'DD', 'PROTEINS_full']:
        return TUsDataset(args.data)
    else:
        raise Exception('Unknown dataset!')


def load_metric(args):
    if args.data in ['ZINC', 'QM9']:
        return MAE
    elif args.data in ['TSP']:
        return binary_f1_score
    elif args.data in ['MNIST', 'CIFAR10']:
        return accuracy_MNIST_CIFAR
    elif args.data in ['SBM_CLUSTER', 'SBM_PATTERN']:
        return accuracy_SBM
    elif args.data in ['Cora']:
        return CoraAccuracy
    elif args.data in ['ENZYMES', 'DD', 'PROTEINS_full']:
        return accuracy_TU
    else:
        raise Exception('Unknown dataset!')
