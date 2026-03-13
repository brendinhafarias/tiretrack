"""
fix_tire_totals.py — Recalcula total_km e total_laps de todos os pneus
a partir das sessões reais no banco.

Uso:
    python fix_tire_totals.py          # preview (sem alterar)
    python fix_tire_totals.py --apply  # aplica a correção
"""
import sys
sys.path.insert(0, '.')

from app import create_app
from app.models import Tire, Session
from app.extensions import db

DRY_RUN = '--apply' not in sys.argv


def main():
    app = create_app('development')
    with app.app_context():
        tires = Tire.query.all()
        changed = 0

        for tire in tires:
            sessions = Session.query.filter_by(tire_id=tire.id).all()

            correct_km   = round(sum(s.km_session or 0 for s in sessions), 3)
            correct_laps = sum(s.laps or 0 for s in sessions)

            km_diff   = abs((tire.total_km   or 0) - correct_km)
            laps_diff = abs((tire.total_laps or 0) - correct_laps)

            if km_diff > 0.01 or laps_diff > 0:
                print(f'Pneu {tire.code} (id={tire.id}):')
                print(f'  total_km:   {tire.total_km:.1f} → {correct_km:.1f}')
                print(f'  total_laps: {tire.total_laps} → {correct_laps}')
                if not DRY_RUN:
                    tire.total_km   = correct_km
                    tire.total_laps = correct_laps
                changed += 1

        if changed == 0:
            print('Nenhum pneu com totais incorretos.')
            return

        print(f'\nTotal de pneus a corrigir: {changed}')

        if DRY_RUN:
            print('\n[DRY RUN] Nada foi alterado. Use --apply para aplicar.')
        else:
            db.session.commit()
            print(f'\n[APLICADO] {changed} pneu(s) corrigido(s).')


if __name__ == '__main__':
    main()
