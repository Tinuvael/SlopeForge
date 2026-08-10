# План миграции архитектуры

## Текущий статус

* **Phase 3A — завершена:** geometry value types, операции и import adapters
  перенесены в канонические слои.
* **Phase 3B — завершена:** стабильные domain entities, Technical Card,
  Assessment Evaluation/DAI/FCI и `AssessmentDomainState` перенесены.
* **Phase 3C — завершена:** чистые Assessment policies отделены от
  state-mutating сервисов, attachment I/O отделён от orchestration и Qt,
  `prototype_2d/` удалён.
* **Phase 3 в целом — завершена.**
* **Phase 4A — завершена:** создание Production BlastEvent и BlastBlock атомарно.
* **Phase 4B1 — завершена:** entity editing load/save, Technical Card, Evaluation
  и lazy Evaluation attachment-owner orchestration перенесены из UI в application.
* **Phase 4B2 — завершена:** archive/restore Area и contour, BlastEvent geometry
  reimport и интерактивные Linked Events стали rollback-safe workflows session;
  Block archive вынесен в отдельный use case и узкий persistence port.
* **Phase 4B в целом — завершена.**
* **Phase 4C — завершена:** Project/Domain/report и Assessment geometry commit orchestration вынесены из Qt.
* **PHASE 4 COMPLETE. Phase 5 — следующая.**

Workflow-сервисы теперь находятся в `application/services/`, чистая политика —
в `domain/`, внешние geometry/file/desktop adapters — в `infrastructure/`.
`AssessmentDomainState` сохраняется до Phase 5. Phase 4 отвечает за
MainWindow/application orchestration и явные use cases; Phase 5 — за отказ от
replace-all persistence.

Phase 2 завершена. Перенос domain/application модулей ниже остаётся будущей работой.
Каждый PR сохраняет инженерные формулы, DAI/FCI, report semantics и текущий UI.

## Последовательность PR

1. **Phase 1 (завершена):** AST-аудит, фактическая классификация, target и ratchets.
2. **Phase 2 (завершена):** извлечены geometry editor и два production dialog;
   workspace host/widget, compatibility window/JSON storage, `ui/prototype_2d` и
   dead DirectoryDialog удалены. Поведение normal entity pages сохранено.
3. **Phase 3:** перенос алгоритмов без redesign, начиная с leaf geometry/importers;
   разорвать `domain <-> technical_card`; разделить attachment policy и Qt/files.
4. **Phase 4:** явные application use cases, прежде всего atomic production
   BlastEvent+BlastBlock, archive, assessment save и reports; облегчить MainWindow.
5. **Phase 5:** заменить replace-all repository focused operations + простая Unit
   of Work; добавить concurrency/transaction integration tests.
6. **Phase 6:** отдельный schema PR с новой migration либо пересозданием disposable
   dev DB: убрать AssessmentWorkspace/Mine/старое attachment ownership только после
   доказательства callers. Никогда не применять `alembic stamp` как замену migration.
7. **Phase 7:** убрать shims, дробить oversized modules по пользе, очистить naming,
   imports, packaging и документы.

Phase 2 сначала извлекла production creation/edit flow, затем удалила workspace;
hidden widget и перенос ownership plan view больше не используются.

## Карта файлов

| CURRENT PATH | TARGET PATH | PHASE | NOTES |
|---|---|---:|---|
| `prototype_2d/domain.py` | `domain/blasting/entities.py`, `domain/assessment/entities.py` | 3 | move stable types first; DTO split later |
| `prototype_2d/models.py` | `domain/geometry/types.py` / `application/dto/geometry.py` | 3 | классифицировать каждый type до split |
| `prototype_2d/geometry.py` | `domain/geometry/operations.py` | 3 | чистые algorithms, behaviour unchanged |
| `prototype_2d/blast_geometry.py` | domain policy + `infrastructure/geometry_import/blast.py` | 3 | отделить I/O от normalization |
| `prototype_2d/technical_card.py` | `domain/blasting/technical_card.py` | 3 | formulas unchanged; убрать import cycle |
| `prototype_2d/wall_assessment.py` | `domain/assessment/evaluation.py` | 3 | DAI/FCI/X/Y unchanged |
| `prototype_2d/domain_geometry.py` | `domain/project/domain_geometry.py` | 3 | pure polygon construction |
| `prototype_2d/csv_importer.py` | `infrastructure/geometry_import/csv.py` | 3 | encoding/delimiter adapter |
| `prototype_2d/dxf_importer.py` | `infrastructure/geometry_import/dxf.py` | 3 | no new DXF dependency required |
| `prototype_2d/line_geometry_importer.py` | `infrastructure/geometry_import/lines.py` | 3 | adapter dispatch |
| `prototype_2d/entity_attachments.py` | `domain/attachments/policy.py` + `application/commands/attachments.py` + `infrastructure/files/attachments.py` | 3–4 | сохранить one-owner, copy rollback; убрать Qt из domain |
| `prototype_2d/blast_event_service.py` | `application/commands/blast_events.py` | 4 | после переноса policies |
| `prototype_2d/assessment_area_service.py` | domain policy + `application/commands/assessment_areas.py` | 3–4 | revision history unchanged |
| `prototype_2d/assessment_event_link_service.py` | domain policy + application command | 3–4 | frozen intersections unchanged |
| `prototype_2d/project_lines_dataset_service.py` | `application/commands/project_lines.py` | 4 | strictly Site-wide |
| `prototype_2d/blast_event_storage.py` | удалить | 2 | только вместе с compatibility window/tests |
| `ui/prototype_2d/blast_event_window.py` | удалить | 2 | no normal navigation caller |
| `ui/directory_dialog.py` | удалить | 2 | DEAD: нет caller; не путать с активным `SiteRepository` в project tree |
| `ui/widgets/assessment_workspace.py` | focused `ui/editors/assessment_geometry_editor.py` + reusable `ui/widgets/*` | 2 | extract, do not big-bang rewrite |
| `ui/pages/assessment_workspace_page.py` | focused creation/edit page or remove host | 2 | active caller is creation page |
| `ui/pages/assessment_area_creation_page.py` | `ui/pages/assessment_area_creation_page.py` | 2 | сохранить path, заменить composition |
| `ui/pages/entity_page_controller.py` | `application/commands/*` + thin UI presenter/controller | 4 | transactions leave UI |
| `ui/main_window.py` | same UI shell + `application/commands/*` | 4 | routing stays; workflows move |
| `repositories/*.py` | `infrastructure/db/repositories/*.py` | 3–7 | gradual moves, no interface-per-repo rule |
| `repositories/assessment_state_repository.py` | focused infrastructure repositories/UoW | 5 | replace-all remains until use cases exist |
| `repositories/assessment_state_mapper.py` | `infrastructure/db/assessment_mapper.py` | 5 | split validation into domain as appropriate |
| `services/project_service.py` | `application/commands/projects.py` | 4 | hide Mine/Site until Phase 6 |
| `services/blast_block_service.py` | `application/commands/production_blocks.py` | 4 | combine event/block transaction |
| `services/project_report_service.py` | application report query + infrastructure reader | 4 | preserve stored completed results |
| other `services/*.py` | `application/` (workflow) or `infrastructure/` (I/O) | 4 | decide by behaviour, not filename |
| `reports/excel_project_report.py` | `infrastructure/reports/excel_project_report.py` | 3–4 | output semantics unchanged |
| `database/*.py` | `infrastructure/db/*.py`; bootstrap parts to `app/` | 6–7 | only after schema/use-case stabilization |
| `widgets/*.py` | `ui/widgets/*.py` | 7 | mechanical imports after hotspots |
| `database.models.Mine`, Mine repository/UI | remove/merge into Project model | 6 | schema PR; normal UI must say Project |
| `database.assessment_models.AssessmentWorkspace` | remove container if focused ownership permits | 6 | keep Domain ownership and transactions |
| legacy/current attachment tables | one explicit owner model | 6 | production owns via linked BlastEvent |

## Tests, которые едут вместе с features

* Phase 2: workspace/window/page tests; сохранить geometry creation behaviour,
  заменить wrapper tests после удаления wrapper.
* Phase 3: `test_technical_card*`, `test_wall_assessment*`, geometry/DXF/CSV,
  event-link и attachment tests меняют imports одновременно с переносом.
* Phase 4: service/MainWindow/report/dashboard tests переходят на use cases;
  добавить atomic create/link integration test.
* Phase 5: mapper/repository PostgreSQL tests переходят на focused operations;
  сохранить full round-trip и добавить rollback/concurrency cases.
* Phase 6: Alembic/startup/model tests меняются только с реальной schema migration.

## Условия завершения

После каждой фазы: architecture audit, boundary tests, полный offscreen pytest,
compileall, `git diff --check`, один Alembic head. Allowlist только уменьшается.

## Результат Phase 2 и следующий долг

Focused editor временно импортирует `prototype_2d.assessment_area_service`,
`assessment_event_link_service`, geometry и domain types. Это ожидаемая граница
Phase 2, а не завершение Phase 3. В Phase 3 без redesign переносятся перечисленные
алгоритмы/import adapters. MainWindow orchestration остаётся до Phase 4, а
`AssessmentStateRepository.replace_for_domain()` — до Phase 5. Схема и Alembic в
Phase 2 не менялись.

## Результат Phase 3A и следующий долг

Phase 3A завершена как отдельная первая часть Phase 3. Канонические пути теперь:
`domain/geometry/types.py`, `domain/geometry/operations.py`,
`domain/geometry/blast.py`, `domain/project/domain_geometry.py` и
`infrastructure/geometry_import/{csv,dxf,lines}.py`. Старые geometry/import
модули `prototype_2d` удалены. Datamine types оставлены в domain, а не в
infrastructure, потому что они входят в сериализацию остающихся domain entities.

Phase 3 целиком **не завершена**. Phase 3B должна перенести BlastEvent,
AssessmentArea, AssessmentDomainState и разорвать цикл domain/technical_card,
после чего удалить временный re-export из `prototype_2d/domain.py`. Phase 3C
может безопасно разделить attachment policy, Qt image metadata и filesystem I/O,
а также оставшиеся assessment/blasting policies. Application workflows,
MainWindow и replace-all persistence остаются соответственно для Phase 4/5.

## Результат Phase 4A и оставшийся долг

**Phase 4A завершена.** Явный `CreateBlastEvent` отделил создание заголовка от
`MainWindow`; production BlastEvent, единственный связанный BlastBlock и его audit
теперь фиксируются одной транзакцией. Contour не создаёт Block. Для этого только
добавлен session-aware вариант существующего replace-all сохранения; его публичное
поведение и схема БД не изменены.

## Результат Phase 4B и оставшийся долг

**Phase 4B1 завершена.** Узкий
`AssessmentStatePersistence` и SQLAlchemy adapter сохраняют старую replace-all
семантику. `AssessmentEditingSession` владеет загрузкой/сохранением живого графа,
Technical Card и Evaluation draft/save rollback, правами и lazy Evaluation owner.
UI controller только делегирует эти workflows и пока связывает attachments/links.

**Phase 4B2 завершена.** `EntityPageController` остался тонким UI adapter и
делегирует archive/reimport/link commands session; link read helpers временно
экспонируются через `editing.links`. Geometry editor по-прежнему обновляет
автоматические suggestions внутри существующей транзакции ревизии границы — её
перенос не входил в 4B2.

**Phase 4C завершена:** Project creation с optional Project Lines, Domain creation, navigation queries, report collect/write и Assessment geometry commit теперь application-owned. Старые misplaced Project/report services удалены. **PHASE 4 COMPLETE.**

## Результат Phase 5A и оставшийся долг

**Phase 5A COMPLETE; Phase 5 NOT COMPLETE.** Совместимый whole-state API сохранён,
но `AssessmentStateRepository` больше не удаляет Workspace. Первый save создаёт
его, последующие используют тот же PK и синхронизируют строки по logical ID на
месте. Неизменные entity/revision PK стабильны, omitted subtree удаляется в
dependency-safe порядке, active flags переключаются через отдельное очистительное
flush, а caller-owned transaction по-прежнему полностью откатывает graph,
BlastBlock и audit. Миграции схемы нет.

**Phase 5B:** заменить обычные application whole-state saves focused workflows:
BlastEvent header/geometry, archive state, Technical Card revision, Assessment Area
geometry revision, Assessment Event Links, Evaluation revision и attachment
metadata/owner. Маленький application Unit of Work вводить только там, где одна
операция действительно меняет несколько сущностей атомарно. В 5A это не сделано.

**Phase 5C:** убрать обычное использование `replace_for_domain()` и совместимый
`AssessmentStatePersistence.save`; добавить защиту от lost updates (пригодный
optimistic version/token), удалить устаревшие compatibility persistence paths и
добавить финальные architecture ratchets. Удаление AssessmentWorkspace, legacy
Mine, redesign attachments и крупные переименования БД остаются отдельной schema /
product cleanup, а не частью Phase 5A.
