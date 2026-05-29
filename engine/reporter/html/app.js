/* SentinelQA HTML report — vanilla interactivity.
 * Handles the findings filter/sort + audit-log filter. No frameworks.
 */
(function () {
  'use strict';

  function filterRows(table, filters) {
    if (!table) return;
    var rows = table.querySelectorAll('tbody tr.finding-row');
    var query = (filters.query || '').trim().toLowerCase();
    var severity = filters.severity || '';
    var module = filters.module || '';
    for (var i = 0; i < rows.length; i++) {
      var row = rows[i];
      var rowSev = row.getAttribute('data-severity') || '';
      var rowMod = row.getAttribute('data-module') || '';
      var rowText = (row.getAttribute('data-search') || '').toLowerCase();
      var hide =
        (severity && rowSev !== severity) ||
        (module && rowMod !== module) ||
        (query && rowText.indexOf(query) === -1);
      row.classList.toggle('is-hidden', !!hide);
    }
  }

  function wireFindings() {
    var table = document.querySelector('table.findings-table');
    if (!table) return;
    var controls = document.querySelector('.findings-controls');
    if (!controls) return;
    var sevSelect = controls.querySelector("select[data-filter='severity']");
    var modSelect = controls.querySelector("select[data-filter='module']");
    var queryInput = controls.querySelector("input[data-filter='query']");
    function update() {
      filterRows(table, {
        severity: sevSelect ? sevSelect.value : '',
        module: modSelect ? modSelect.value : '',
        query: queryInput ? queryInput.value : '',
      });
    }
    if (sevSelect) sevSelect.addEventListener('change', update);
    if (modSelect) modSelect.addEventListener('change', update);
    if (queryInput) queryInput.addEventListener('input', update);
  }

  function wireAudit() {
    var list = document.querySelector('ul.audit-list');
    if (!list) return;
    var controls = document.querySelector('.audit-controls');
    if (!controls) return;
    var levelSelect = controls.querySelector("select[data-filter='audit-level']");
    var moduleSelect = controls.querySelector("select[data-filter='audit-module']");
    function update() {
      var level = levelSelect ? levelSelect.value : '';
      var module = moduleSelect ? moduleSelect.value : '';
      var items = list.querySelectorAll('li.audit-entry');
      for (var i = 0; i < items.length; i++) {
        var item = items[i];
        var rowLevel = item.getAttribute('data-level') || '';
        var rowMod = item.getAttribute('data-module') || '';
        var hide = (level && rowLevel !== level) || (module && rowMod !== module);
        item.classList.toggle('is-hidden', !!hide);
      }
    }
    if (levelSelect) levelSelect.addEventListener('change', update);
    if (moduleSelect) moduleSelect.addEventListener('change', update);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () {
      wireFindings();
      wireAudit();
    });
  } else {
    wireFindings();
    wireAudit();
  }
})();
