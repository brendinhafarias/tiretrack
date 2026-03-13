"""
cleanup_duplicate_sessions.py — Remove sessões duplicadas do banco.

Para cada combinação (tire_id, set_id, date, event_type), mantém apenas
a sessão com menor ID (a primeira registrada) e apaga as demais.

Uso:
    python cleanup_duplicate_sessions.py          # preview (sem apagar)
    python cleanup_duplicate_sessions.py --apply  # aplica a limpeza
"""
import sys
from collections import defaultdict

sys.path.insert(0, '.')

from app import create_app
from app.models import Session, Tire
from app.extensions import db

DRY_RUN = '--apply' not in sys.argv


def main():
    app = create_app('development')
    with app.app_context():
        # Busca todas as sessões com set_id definido
        all_sessions = (
            Session.query
            .filter(Session.set_id.isnot(None))
            .order_by(Session.tire_id, Session.set_id, Session.date, Session.event_type, Session.id)
            .all()
        )

        # Agrupa por (tire_id, set_id, date, event_type)
        groups = defaultdict(list)
        for s in all_sessions:
            key = (s.tire_id, s.set_id, s.date.isoformat(), s.event_type)
            groups[key].append(s)

        to_delete = []
        for key, sessions in groups.items():
            if len(sessions) > 1:
                keep = sessions[0]  # menor ID = primeira registrada
                dupes = sessions[1:]
                tire = Tire.query.get(key[0])
                print(f'\nDuplicata: tire={tire.code if tire else key[0]} '
                      f'set_id={key[1]} date={key[2]} event={key[3]}')
                print(f'  Manter:  id={keep.id} laps={keep.laps}')
                for d in dupes:
                    print(f'  Apagar:  id={d.id} laps={d.laps}')
                to_delete.extend(dupes)

        if not to_delete:
            print('Nenhuma sessão duplicada encontrada.')
            return

        print(f'\nTotal a apagar: {len(to_delete)} sessões')

        if DRY_RUN:
            print('\n[DRY RUN] Nada foi apagado. Use --apply para aplicar.')
        else:
            delete_ids = {s.id for s in to_delete}
            affected_tire_ids = {s.tire_id for s in to_delete if s.tire_id}

            for s in to_delete:
                db.session.delete(s)
            db.session.flush()

            # Recompute tire totals from remaining sessions
            from app.models import Tire
            for tid in affected_tire_ids:
                tire = Tire.query.get(tid)
                if not tire:
                    continue
                remaining = Session.query.filter_by(tire_id=tid).all()
                tire.total_km   = round(sum(s.km_session or 0 for s in remaining), 3)
                tire.total_laps = sum(s.laps or 0 for s in remaining)

            db.session.commit()
            print(f'\n[APLICADO] {len(to_delete)} sessões duplicadas removidas.')
            print(f'Totais de {len(affected_tire_ids)} pneu(s) recalculados.')


if __name__ == '__main__':
    main()
