"""A reply proposal cannot leave a previously approved campaign releasable."""
import pytest
from conftest import approve_synthetic, prepare_release

from pipeline import agency, clarifications, delivery, gates, question_exchange, revisions


def test_reply_blocks_approved_release_until_explicit_review(tmp_path):
    run = prepare_release(tmp_path)
    brief = revisions.load(run/'brief.json')
    brief['open_questions'] = [{'field':'budget', 'gap':'Unknown reviewer', 'why_it_matters':'Planning',
                               'suggested_question_for_client':'Who reviews?',
                               'linked_evidence':brief['objectives'][0]['evidence']}]
    brief['readiness'] = gates.compute_readiness_block(brief)
    revisions.write_json(run/'brief.json', brief)
    for lang in ('el','en'):
        with (run/f'brief_{lang}.md').open('a') as handle:
            handle.write('\n## ⚠ Open questions\n1. Who reviews? [rfp L1]\n')
    queue = clarifications.queue(brief)
    clarifications.record(
        run, queue, queue[0]['id'], 'open', 'Synthetic lead', 'Can wait', '', 'Synthetic account', 'nonblocking'
    )
    approve_synthetic(run)
    delivery.register(run, tmp_path/'draft.txt', 'Synthetic operator')
    delivery.approve(run, 'Synthetic lead', 'Reviewed', delivery.CHECKS)
    pack = question_exchange.export_questions(run, tmp_path/'questions.json')
    reply = {'pack_id':pack['pack_id'], 'replies':[{'question_id':queue[0]['id'],'text':'Proposed new reviewer',
             'evidence':{'source_ref':'Synthetic reply 1','provided_by':'Synthetic respondent'}}]}
    proposal = question_exchange.import_replies(run, pack, reply, 'Synthetic importer')
    assert any('Unreviewed clarification' in p for p in agency.audit(run, persist=False)['blockers'])
    with pytest.raises(ValueError, match='Unreviewed clarification'):
        delivery.release(run, tmp_path/'blocked', 'Synthetic releaser')
    question_exchange.dismiss(
        run, proposal['proposal_id'], actor='Synthetic lead', reason='Wrong campaign; verified irrelevant'
    )
    assert delivery.release(run, tmp_path/'approved', 'Synthetic releaser').is_dir()
