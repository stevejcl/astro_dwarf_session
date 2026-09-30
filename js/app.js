import { openDwarfProgramPanel } from './dwarf-scheduler.js';

document.addEventListener('DOMContentLoaded', () => {
  const btnProgram = document.getElementById('btn-program-selected');

  if (btnProgram) {
    btnProgram.addEventListener('click', () => {
      // 1. Récupération des cibles cochées dans le DOM
      const checkboxes = document.querySelectorAll('.target-checkbox:checked');

      const selectedTargets = Array.from(checkboxes).map(cb => ({
        id: cb.dataset.id,
        name: cb.dataset.name,
        ra: parseFloat(cb.dataset.ra),
        dec: parseFloat(cb.dataset.dec),
        filterRec: { subSec: '15', gain: '80', filterId: 'dwarf-astro' }
      }));

      // 2. Ouverture du panneau de programmation
      openDwarfProgramPanel(selectedTargets, { title: 'Ma Sélection Personnalisée' });
    });
  }
});