/**
 * Contract tests pinning the session_snapshot parser to the briefing:
 * status in `active | interrupted | closed`, default agent `first_line_cx`.
 */
import { normalizeAgentId, normalizeSessionStatus, parseAgentChatStreamEvent } from '../lib/supportAgentChatClient';

describe('session status/identity briefing contract', () => {
  it.each([
    ['active', 'active'],
    ['interrupted', 'interrupted'],
    ['closed', 'closed'],
    ['streaming', 'active'],
    ['disconnected', 'interrupted'],
    ['nonsense', 'active'],
  ])('normalizes %s -> %s', (raw, expected) => {
    expect(normalizeSessionStatus(raw)).toBe(expected);
  });

  it('maps empty and legacy agent ids to first_line_cx', () => {
    expect(normalizeAgentId('')).toBe('first_line_cx');
    expect(normalizeAgentId('trackflow-support-agent')).toBe('first_line_cx');
    expect(normalizeAgentId('first_line_cx')).toBe('first_line_cx');
  });

  it('parseAgentChatStreamEvent normalizes legacy snapshot status and defaults agent_id', () => {
    const event = parseAgentChatStreamEvent(
      JSON.stringify({
        event: 'session_snapshot',
        thread_id: 'thr_1',
        session_id: 'sess_1',
        user_id: 'usr_client_01',
        client_id: 'trackflow-backoffice',
        status: 'streaming',
        session: { session_id: 'sess_1', thread_id: 'thr_1', user_id: 'usr_client_01', status: 'disconnected' },
        messages: [],
        pending_proposal: null,
        latest_checkpoint_id: null,
        checkpoint_count: 0,
        sequence_id: 0,
        timestamp: '2026-11-25T12:00:00Z',
      })
    );
    expect(event?.event).toBe('session_snapshot');
    if (event?.event === 'session_snapshot') {
      expect(event.status).toBe('active');
      expect(event.session.status).toBe('active');
      expect(event.session.agent_id).toBe('first_line_cx');
      expect(event.user_id).toBe('usr_client_01');
    }
  });

  it('parseAgentChatStreamEvent never falls back to owner_user_id and defaults missing client user_id to unassigned', () => {
    const event = parseAgentChatStreamEvent(
      JSON.stringify({
        event: 'session_snapshot',
        thread_id: 'thr_1',
        session_id: 'sess_1',
        owner_user_id: 'operator_should_not_leak',
        client_id: 'trackflow-backoffice',
        status: 'active',
        session: { session_id: 'sess_1', thread_id: 'thr_1', status: 'active' },
        messages: [],
        pending_proposal: null,
        latest_checkpoint_id: null,
        checkpoint_count: 0,
        sequence_id: 0,
        timestamp: '2026-11-25T12:00:00Z',
      })
    );
    expect(event?.event).toBe('session_snapshot');
    if (event?.event === 'session_snapshot') {
      expect(event.user_id).toBe('unassigned');
      expect(event.session.user_id).toBe('unassigned');
    }
  });
});
