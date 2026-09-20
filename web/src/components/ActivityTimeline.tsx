import type { ActivityEvent } from '../types'

function describeEvent(event: ActivityEvent): string {
  if (event.event_type === 'created') {
    return `Created (${event.to_status})`
  }
  return `Status changed: ${event.from_status} → ${event.to_status}`
}

/** Creation + status changes only (see CLAUDE.md) - the API already
 * returns these newest-first, so no client-side sort is needed here. */
export function ActivityTimeline({ events }: { events: ActivityEvent[] }) {
  return (
    <section className="activity-timeline">
      <h2>Activity</h2>
      {events.length === 0 ? (
        <p className="empty">No activity recorded yet.</p>
      ) : (
        <ul>
          {events.map((event) => (
            <li key={event.id}>
              <span className="activity-description">{describeEvent(event)}</span>
              <span className="activity-timestamp">{new Date(event.occurred_at).toLocaleString()}</span>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
