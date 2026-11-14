"""Head archetypes for the family generators (DESIGN.md: canid, feline, reptile / raptor, bird, insect, fish, primate,
serpent). Each module places its head's landmarks in its own frame, so the skeleton (W1) and the head block-out (W2)
read one table (AG 05.4: joint positions from the pivot data the geometry builder uses). canid is the first
(WOLF_PLAN.md §4.1)."""
import importlib


def archetype(name):
    """the head archetype module by name (SPEC['head_archetype'])"""
    return importlib.import_module(f'{__name__}.{name}')
