import { ExternalLink } from 'lucide-react';
import { SectionHeading } from '../components/SectionHeading';
import { team } from '../data/site';

export function TeamPage() {
  return (
    <div className="page-wrap">
      <section className="page-hero section-wrap">
        <span className="eyebrow">The team</span>

        <h1>Four data engineers behind Sentinel.</h1>

        <p>
          Meet the team behind Sentinel and the areas each member contributed
          to throughout the project.
        </p>
      </section>

      <section className="section-wrap section-block">
        <SectionHeading
          eyebrow="Built together"
          title="Meet the team behind the experiment."
        />

        <div className="team-grid">
          {team.map((member, index) => (
            <article className="team-card" key={member.name}>
              <div className="avatar-placeholder">
                {String(index + 1).padStart(2, '0')}
              </div>

              <span className="member-kicker">
                Team member {index + 1}
              </span>

              <h2>{member.name}</h2>

              <strong>{member.role}</strong>

              {(member.linkedin || member.portfolio) && (
                <div className="member-links">
                  {member.linkedin && (
                    <a
                      href={member.linkedin}
                      target="_blank"
                      rel="noreferrer"
                    >
                      LinkedIn
                      <ExternalLink size={13} />
                    </a>
                  )}

                  {member.portfolio && (
                    <a
                      href={member.portfolio}
                      target="_blank"
                      rel="noreferrer"
                    >
                      Portfolio
                      <ExternalLink size={13} />
                    </a>
                  )}
                </div>
              )}
            </article>
          ))}
        </div>
      </section>
    </div>
  );
}