# Архитектура SlopeForge: текущее состояние и целевая модель

Статус документа: **Phase 1**, аудит среза `0762eadd9810e18d3b0f43abc08a5abb760113f9`.
Это описание фактического кода, а не уже выполненный рефакторинг. Схема БД и
поведение продукта в этой фазе не меняются.

## Неподвижные правила продукта

* В интерфейсе `Site` означает **Project / Quarry**; `Mine` — только временная
  внутренняя совместимость и не часть обычного UI.
* Project → Domain → Blast events / Assessment areas. Horizon и Elevation
  Interval — виртуальные группы дерева, не таблицы.
* Project Lines принадлежат Site целиком. Геометрия Assessment Area версионная.
* `BlastEvent` один: production имеет связь 1:1 с `BlastBlock`, contour не имеет
  блока. Связанные production-сущности нельзя считать дважды.
* DAI и FCI различны; в quadrant X=FCI, Y=DAI. Завершённая историческая оценка
  показывает сохранённый результат.
* Физический attachment имеет одного владельца: production/contour через
  `BlastEvent`, Assessment Area через evaluation.
* Формулы Technical Card, scoring и смысл отчётов при переносах не изменяются.

## Метод аудита и общий результат

`tools/architecture_audit.py` разбирает AST всех production-модулей, строит
module/layer edges, специальные списки связей и strongly connected components.
Он не импортирует приложение, поэтому результат не зависит от Qt или БД.

Сейчас приложение — рабочий слоистый MVP, но границы проходят по истории файлов,
а не по ответственности:

* `main.py` и `app/` загружают конфигурацию, Qt, локализацию и контекст;
* `ui/` содержит presentation, но также создаёт сервисы, вызывает repositories,
  управляет транзакционными откатами и импортом;
* `prototype_2d/` фактически содержит ядро assessment/blasting, use-case-подобные
  сервисы, import adapters и файловую логику одновременно;
* `repositories/` и `database/` — SQLAlchemy persistence; `services/` смешивает
  application workflows и инфраструктурный доступ;
* `reports/` — Excel infrastructure; корневой `widgets/` — активный старый UI.

AST-аудит обнаруживает зависимости `UI -> repositories/database/services`, много
`UI/repositories -> prototype_2d` и цикл `prototype_2d.domain <->
prototype_2d.technical_card`. Из domain-like модулей только
`entity_attachments.py` импортирует PySide6 (QImage/QBuffer), что подтверждает
смешение policy и image/file adapter.

## Единая классификация важных областей

Классы: **ACTIVE** — нормальный runtime и подходящее место;
**ACTIVE_BUT_MISPLACED** — нормальный runtime, неверный слой;
**COMPATIBILITY_ONLY** — тесты/старый инструмент/переходный caller;
**DEAD** — нет production, tests, migrations, CLI или packaging caller.

| Область / модули | Класс | Доказательство и замечание |
|---|---|---|
| `main.py`, `app/*.py` | ACTIVE | bootstrap/config/localization/Qt platform используются запуском |
| `database/*.py` | ACTIVE | текущая SQLAlchemy-модель, startup, auth и AppContext; legacy-сущности отдельно отмечены ниже |
| `repositories/assessment_state_mapper.py`, `assessment_state_repository.py`, `attachment_repository.py`, `audit_log_repository.py`, `blast_block_repository.py`, `dashboard_repository.py`, `domain_geometry_repository.py`, `domain_repository.py`, `navigation_repository.py`, `project_lines_repository.py`, `site_repository.py`, `user_repository.py` | ACTIVE | production persistence, расположение временно приемлемо до переноса в infrastructure |
| `repositories/mine_repository.py` | COMPATIBILITY_ONLY | вызывается только старым `DirectoryDialog`; обычный Project flow использует `ProjectService` |
| `services/*.py` | ACTIVE_BUT_MISPLACED | активные workflow/service-фасады, будущий `application/`; DB-specific детали затем отделить |
| `reports/*.py` | ACTIVE_BUT_MISPLACED | активный Excel I/O, будущий `infrastructure/reports/` |
| `ui/pages/*`, `ui/dialogs/*`, `ui/editors/*`, `ui/widgets/plan_view.py`, обычные `ui/*.py` | ACTIVE | нормальная навигация/presentation, кроме явно перечисленных переходных контейнеров |
| `ui/pages/entity_page_controller.py` | ACTIVE_BUT_MISPLACED | активный persistence/application coordinator внутри UI |
| `ui/pages/assessment_workspace_page.py` | ACTIVE_BUT_MISPLACED | нужен production-потоку создания/правки границ, но является переходным host старого workspace |
| `ui/widgets/assessment_workspace.py` | ACTIVE_BUT_MISPLACED | 1262-строчный активный «всё-в-одном» workspace; содержит пригодные widgets и workflow logic |
| `ui/prototype_2d/blast_event_window.py` | COMPATIBILITY_ONLY | нет production caller; wrapper и JSON storage проверяются тестами |
| `ui/prototype_2d/__init__.py` | COMPATIBILITY_ONLY | package marker для wrapper/tests |
| корневой `widgets/*.py` | ACTIVE_BUT_MISPLACED | активные presentation widgets, должны со временем стать `ui/widgets/` |
| `alembic/` | ACTIVE | история текущей схемы и startup/integration checks; не runtime UI |
| `tests/` | ACTIVE | regression safety net, хотя часть тестов структурно связана с legacy |
| старые документы в `docs/` | ACTIVE | инженерная/операционная документация, не executable dependencies |

На этом срезе **не найден ни один достаточно доказанный DEAD Python-модуль**.
Отсутствие прямого production import недостаточно: import adapters вызываются
косвенно, а wrapper/storage используются тестами и старым инструментом. Кандидат
на удаление после Phase 2 — `ui/prototype_2d/blast_event_window.py` вместе с
`prototype_2d/blast_event_storage.py`: production imports отсутствуют, migrations,
CLI и spec их не называют, но сейчас их требуют wrapper/storage tests, поэтому
класс строго `COMPATIBILITY_ONLY`, не DEAD.

## Полная классификация `prototype_2d`

| Текущий путь | Класс | Ответственность | Важные callers / зависимости | Будущее место | Риск; фаза |
|---|---|---|---|---|---|
| `__init__.py` | ACTIVE | package marker активного ядра | все prototype imports | удалить после переносов | low; 7 |
| `domain.py` | ACTIVE_BUT_MISPLACED | entities, revisions, aggregate state, serialization | repositories, pages/widgets; `models`, technical card, assessment | `domain/blasting/` + `domain/assessment/` + application DTO при разделении | very high; 3, без redesign |
| `models.py` | ACTIVE_BUT_MISPLACED | import/geometry value DTO | domain/importers/tests | `domain/geometry/` либо `application/dto/` по типу | medium; 3 |
| `geometry.py` | ACTIVE_BUT_MISPLACED | чистая plan-geometry validation/intersection | area/link/domain geometry, editors | `domain/geometry/` | high; 3 |
| `blast_geometry.py` | ACTIVE_BUT_MISPLACED | blast geometry import/normalization | BlastEventService/tests; domain/models | domain policy + geometry adapter split | high; 3 |
| `technical_card.py` | ACTIVE_BUT_MISPLACED | неизменяемые engineering calculations и revision service | editors/controller/tests; цикл с `domain` | `domain/blasting/technical_card.py` | very high; 3 |
| `wall_assessment.py` | ACTIVE_BUT_MISPLACED | DAI/FCI models, validation, scoring/revisions | editor/controller/repository/report tests | `domain/assessment/evaluation.py` | very high; 3 |
| `blast_event_service.py` | ACTIVE_BUT_MISPLACED | create/import BlastEvent workflow | MainWindow, pages, workspace | `application/commands/blast_events.py` с чистыми policies в domain | high; 4 (после 3) |
| `assessment_area_service.py` | ACTIVE_BUT_MISPLACED | area creation and geometry workflow | active workspace/tests | application command + domain policy | high; 3–4 |
| `assessment_event_link_service.py` | ACTIVE_BUT_MISPLACED | вычисляет и подтверждает revision links | controller/workspace/report tests | domain linking policy + application command | high; 3–4 |
| `project_lines_dataset_service.py` | ACTIVE_BUT_MISPLACED | import/version/activate dataset in state | MainWindow, dashboard, workspace | `application/commands/project_lines.py` | high; 4; Project/Site scope сохранить |
| `domain_geometry.py` | ACTIVE_BUT_MISPLACED | строит Domain polygons из lines | domain dashboard/tests | `domain/project/domain_geometry.py` | medium; 3 |
| `line_geometry_importer.py` | ACTIVE_BUT_MISPLACED | dispatch CSV/DXF and normalize lines | domain dashboard, dataset/event services | `infrastructure/geometry_import/` | medium; 3 |
| `csv_importer.py` | ACTIVE_BUT_MISPLACED | CSV decoding/delimiter/column parsing | line importer/workspace/dialog/tests | `infrastructure/geometry_import/csv.py` | medium; 3 |
| `dxf_importer.py` | ACTIVE_BUT_MISPLACED | ASCII DXF adapter | line importer/tests | `infrastructure/geometry_import/dxf.py` | medium; 3 |
| `entity_attachments.py` | ACTIVE_BUT_MISPLACED | ownership policy + copy/delete + Qt image metadata | controller/dialog/workspace/tests | policy in domain, workflow in application, bytes/images in `infrastructure/files/` | very high; 3–4 |
| `blast_event_storage.py` | COMPATIBILITY_ONLY | legacy JSON save/load | compatibility window and tests only | удалить вместе с wrapper | medium; 2 |

## UI compatibility и assessment workspace

Обычные entity pages (`block_page`, `contour_event_page`, `assessment_area_page`)
не импортируют `ui.prototype_2d`. Они используют активный
`EntityPageController`, который всё ещё сохраняет весь aggregate.

`AssessmentAreaCreationPage` всё ещё композиционно завязан на
`AssessmentWorkspacePage`, а тот — на огромный `AssessmentWorkspaceWidget`.
Значит, эти два workspace-модуля нельзя удалить в начале Phase 2. Из widget надо
сначала извлечь используемые creation/edit workflow и reusable canvas/dialog
части. `ui/prototype_2d/blast_event_window.py` — отдельный compatibility wrapper;
его normal navigation не вызывает.

## Hotspot: `MainWindow`

Сейчас класс одновременно:

1. строит widgets и связывает signals; маршрутизирует Site/Domain/block/contour/area;
2. хранит выбранный контекст и управляет lifecycle transient pages;
3. конструирует repositories/services и делает прямые запросы;
4. создаёт Project, Domain, BlastEvent и связанный production BlastBlock;
5. вручную координирует два persistence-механизма и компенсирующий rollback при
   ошибке создания production event;
6. сохраняет/откатывает незавершённую assessment geometry при переходе;
7. архивирует block/event/area разными путями;
8. запускает Project Excel report dialog;
9. обновляет tree, search, add/archive permissions и показывает ошибки.

Навигация, lifecycle страниц и presentation остаются в UI. Create/archive,
production event↔block atomicity, сохранение/rollback, report request и получение
context должны стать явными application use cases в Phase 4.

## Hotspot: `AssessmentStateRepository`

`replace_for_domain()` сначала валидирует весь `AssessmentDomainState`, затем в
одном `session.begin()` проверяет Domain, загружает прежний Workspace, удаляет его
с cascade, делает `flush`, создаёт новый Workspace и заново вставляет весь граф.
Реконструируются BlastEvent, все blast geometry revisions, event links, Technical
Card и revisions, Assessment Area и geometry revisions, evaluations/revisions и
assessment attachments. Site-wide ProjectLines datasets только читаются и
проверяются; Domain save их не переписывает. После insert граф перечитывается до
commit. Исключение откатывает всю транзакцию.

Плюсы MVP-подхода: один простой round-trip contract, атомарность, стабильные
domain IDs, лёгкое восстановление in-memory state, отсутствие частично
сохранённого графа. Риски: любое малое изменение вызывает delete/reinsert всего
Domain graph; меняются DB primary keys/workspace ID; растут lock/write volume и
стоимость загрузки; cascade усложняет внешние ссылки; параллельные редакторы могут
перезаписать изменения; attachment rows тоже пересоздаются. Для прототипа это
разумно, но с ростом истории и интеграций станет плохо масштабироваться. Phase 5
добавит focused operations и понятную Unit of Work, не раньше стабилизации use cases.

## Hotspot: `AssessmentDomainState`

Это одновременно:

* in-memory aggregate/workspace state: datasets, events, areas, cards,
  evaluations, attachments;
* DTO между UI/services/repository;
* persistence serialization contract (`to_dict/from_dict`, JSON compatibility);
* контейнер UI редактирования и rollback/deepcopy;
* источник cross-entity lookup/invariants.

Он не является «чистым aggregate» в строгом смысле: Site-wide datasets соседствуют
с Domain-owned graph, UI мутирует списки напрямую, а mapper использует ту же форму.
В Phase 3 сначала переносим поведение без изменений; разделение aggregate/DTO и
workspace session — только после появления use cases, чтобы не сломать semantics.

## Database compatibility

* `Mine -> Site` — историческая пара. Новый ProjectService создаёт обе строки с
  одинаковым именем. `MineRepository`/`DirectoryDialog` остаются legacy UI.
* `AssessmentWorkspace` — технический 1:1 контейнер Domain, а не продуктовая
  сущность. Он является cascade root для events/areas и нужен replace-all.
* Есть параллельные attachment concepts: старый общий `Attachment`/
  `AttachmentRepository` для BlastBlock и новый `AssessmentEntityAttachment` для
  BlastEvent/evaluation. При упрощении надо сохранить правило одного владельца и
  production ownership через linked BlastEvent.
* `BlastBlock` и assessment-schema `BlastEvent` — разные таблицы с nullable unique
  link; это допустимо, если отчёты/dashboard не считают пару дважды.
* Project Lines уже Site-scoped; `domain_id` внутри dataset — стабильный string ID
  объекта, не FK Domain, несмотря на опасное имя.

Схему меняем только в Phase 6 после поведенческих use cases и integration tests.

## Цель: прагматичный modular monolith

```text
UI -> Application -> Domain
        ^             ^
        |             |
   Infrastructure ----+
        ^
        |
 app/bootstrap связывает concrete implementations
```

* `app/`: bootstrap, config, localization, application context.
* `domain/`: project, blasting, assessment и только чистые attachment policies.
  Никаких PySide6, SQLAlchemy, dialogs, Excel, UI filesystem operations или
  concrete PostgreSQL session.
* `application/`: команды/queries/DTO, transaction и workflow orchestration.
  Никаких QWidget/QDialog/pages. Ports вводятся только там, где дают пользу.
* `infrastructure/`: SQLAlchemy/PostgreSQL, CSV/DXF/files, Excel/report I/O.
* `ui/`: PySide6 presentation, input, navigation; без engineering calculations и
  по возможности без transaction choreography.

Это один desktop deployable, не microservices. Не нужны DI framework, event bus,
CQRS framework или generic `Repository[T]`.

## Карта владения features

| Feature | Domain | Application | Infrastructure | UI |
|---|---|---|---|---|
| Project | naming/policies | create/archive/select | Site/Mine persistence | project dialog/tree/dashboard |
| Domain | entity/policies | create/select/archive | Domain repository | tree/domain dashboard |
| Project Lines | immutable geometry/version rules | import/activate/query Site dataset | CSV/DXF + DB | import dialog/site view |
| Blast Event | production/contour invariant, revisions | create/link/archive | event persistence | event pages/dialogs |
| Production Block | block/event link invariant | atomic create/update | block/event repositories | BlockPage |
| Contour Blast | BlastEvent without block | create/edit/archive | event repository | ContourEventPage |
| Technical Card | calculations/revisions unchanged | edit/complete | persistence | editor/cards |
| Assessment Area | aggregate rules | create/edit/archive | persistence | pages/workspace extraction |
| Assessment Geometry | revision/link policies | import/select/revise | geometry persistence/import | plan editor |
| Evaluation / DAI / FCI | scoring and frozen completed result | draft/complete/query | revision persistence | evaluation editor/quadrant |
| Attachments | owner policy | attach/delete/list | storage, metadata/image adapter, DB | previews/dialog |
| Dashboards | metric meaning only | snapshot queries | optimized SQL | charts/pages |
| Reports | report data meaning | request/build dataset | Excel writer + DB reads | report dialog/page |

## Test architecture findings

Must survive moves: technical-card actual/calculation tests, DAI/FCI and persisted
completed-result tests, geometry/link/history tests, import tests, attachment
ownership tests, report semantics, localization, archive/read-only and PostgreSQL
integration tests.

Coupled tests to migrate deliberately:

* `test_blast_event_prototype.py`, `test_assessment_workspace_widget.py` and
  `test_blast_event_window_wrapper.py` know prototype/workspace containers;
* `test_assessment_workspace_page.py` mocks internal widget/repository shape;
* `test_mvp_ui_hardening.py`, `test_dashboard_regressions.py`,
  `test_project_report_ui_polish.py` contain source-text assertions. Они полезны
  как временные ratchets, но затрудняют rename/move;
* repository PostgreSQL tests правильно покрывают границу, но fixtures напрямую
  знают `AssessmentWorkspace` и replace-all schema.

При переносе сначала сохранить behavioural tests, затем заменить source-text
проверки API/Qt behaviour. Не хватает integration boundary для атомарного
production BlastEvent+BlastBlock и конкурентного сохранения assessment state.

## Автоматические guardrails и текущий debt baseline

`tests/test_architecture_boundaries.py` запрещает новые imports normal pages →
`ui.prototype_2d`, новых callers compatibility UI, новые файлы внутри
`ui/prototype_2d`, новые production packages `prototype_*`, новый Qt в чистых
prototype algorithms и `Mine` вне явного списка.

Небольшой baseline разрешает только существующие package paths, два compatibility
UI файла, Qt-долг `entity_attachments.py` и восемь Mine-compatibility файлов.
Baseline — код, а не огромный snapshot imports; его следует только сокращать.

