"""eidoblend.trees: SeedThree trees and plants for Blender films (make_seed_tree).
Guide: tools-guides/trees.md."""

from .seedthree_api import make_seed_tree, find_seedthree, raw

describe = make_seed_tree.describe

__all__ = ['make_seed_tree', 'describe', 'find_seedthree', 'raw']
