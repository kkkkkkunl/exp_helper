"""Compatibility and snapshot checks for Markdown-embedded stage templates."""
import copy
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
import _common as C
import stage_templates as T


def data():
    return {'version': 1, 'stages': [{'id': 'cells', 'title': 'Cells', 'entry': True,
        'pause_after': False, 'requires': [], 'input_types': ['cells'], 'outputs': [],
        'next': [], 'steps': [{'id': 'record', 'title': 'Record', 'fields': []}]}]}


def markdown(body=None):
    return '---\nrecord_type: method_template\n---\n\n## Method\n\n```yaml\nexample: true\n```\n\n```yaml experiment-workflow\n' + (body or C._yamlish.dumps(data())) + '```\n'


class EmbeddedStages(unittest.TestCase):
    def test_raw_yaml_and_embedded_yaml_are_equivalent(self):
        self.assertEqual(T.parse_content(C._yamlish.dumps(data())), data())
        self.assertEqual(T.parse_content(markdown()), data())

    def test_tilde_fences_and_longer_closing_fences(self):
        text = '~~~yaml experiment-workflow\n' + C._yamlish.dumps(data()) + '~~~~\n'
        self.assertEqual(T.parse_content(text), data())

    def test_ambiguous_and_unclosed_blocks_are_rejected(self):
        with self.assertRaises(C.SkillError): T.parse_content(markdown() + markdown())
        with self.assertRaises(C.SkillError): T.parse_content(markdown().rsplit('```', 1)[0])
        with self.assertRaises(C.SkillError):
            T.parse_content('```yaml experiment-workflow\n' + C._yamlish.dumps(data()) + '~~~\n')

    def test_unmarked_yaml_and_nested_example_are_not_selected(self):
        with self.assertRaises((C.SkillError, ValueError)):
            T.parse_content('## Example\n```yaml\n' + C._yamlish.dumps(data()) + '```\n')
        text = '````markdown\n' + markdown() + '\n````\n' + markdown()
        self.assertEqual(T.parse_content(text), data())

    def test_snapshot_preserves_entire_markdown_and_rejects_tampering(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            p = SimpleNamespace(root=root, experiment_dir=lambda eid: root / eid)
            source = root / 'template.md'
            source.write_text(markdown(), encoding='utf-8')
            template = T.load(p, {'path': 'template.md', 'name': 'cells', 'format': 'staged', 'version': '1'})
            snapshot = T.freeze(p, 'synthetic', template)
            source.write_text('changed', encoding='utf-8')
            self.assertEqual(T.frozen(p, snapshot), template)
            altered = copy.deepcopy(template)
            altered['data']['stages'][0]['title'] = 'changed parsed value'
            (root / snapshot['path']).write_text(C.json_text(altered), encoding='utf-8')
            with self.assertRaises(C.SkillError): T.frozen(p, snapshot)

    def test_delivered_cell_template(self):
        path = Path(__file__).resolve().parents[1] / 'assets' / 'qPCR.md'
        parsed = T.parse_content(path.read_text(encoding='utf-8'))
        self.assertEqual([s['id'] for s in parsed['stages']], ['cells', 'rna', 'rt', 'qpcr', 'results'])
        self.assertEqual(parsed['stages'][0]['input_types'], ['cells'])
        self.assertFalse(any(s['pause_after'] for s in parsed['stages']))
        for stage in parsed['stages']:
            for step in stage['steps']:
                for field in step['fields']:
                    if field['measurement']: self.assertNotIn('default', field)


if __name__ == '__main__': unittest.main()
