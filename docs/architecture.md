# Архитектура SlopeForge: текущее состояние и целевая модель

## Исторический статус до Phase 4C

Phase 3A, 3B и 3C завершены. Временный пакет `prototype_2d` полностью удалён:
стабильные сущности и чистые правила находятся в `domain/`, переходные сервисы,
которые меняют `AssessmentDomainState`, — в `application/services/`, а импорт
геометрии и физическое хранение файлов — в `infrastructure/`. Qt-открытие файлов
изолировано в desktop-адаптере инфраструктуры; `domain/` и `application/` Qt не
импортируют.

Чистая геометрическая политика Assessment Area находится в
`domain/assessment/geometry.py`, политика сопоставления событий — в
`domain/assessment/event_links.py`, attachment-категории и безопасные имена — в
`domain/attachments/policy.py`. Оркестрация вложений с прежними гарантиями
rollback осталась application-сервисом, а copy/move/delete/path выполняет
`infrastructure/files/attachments.py`.

`AssessmentDomainState` остаётся переходным долгом до Phase 5. Очистка
оркестрации `MainWindow` и явные use cases остаются задачей Phase 4. Replace-all
persistence остаётся без изменений до Phase 5.

Этот раздел фиксирует историческое состояние после Phase 4B; актуальный итог Phase 4C описан ниже. Replace-all persistence по-прежнему отложен до Phase 5.

## Статус после Phase 4C — PHASE 4 COMPLETE

**Phase 4A завершена. Phase 4B завершена. Phase 4C завершена. PHASE 4 COMPLETE.**

Финальный поток записи Phase 4:

```text
Qt UI
  -> application use case / AssessmentEditingSession
  -> application port
  -> infrastructure adapter
  -> SQLAlchemy / files / OpenPyXL
```

Создание Project (включая предварительную проверку и последующее сохранение
Project Lines), создание Domain и сбор+запись Project report теперь принадлежат
application use cases. MainWindow отвечает только за диалоги, навигацию и сообщения.
Создание/ревизия геометрии Assessment Area, автоматический поиск links, частичный
успех поиска и rollback живого графа при ошибке сохранения принадлежат
`AssessmentEditingSession`; geometry editor оставляет у себя рисование и preview.
SQL report query находится в `infrastructure/db/project_report.py`, а OpenPyXL writer
реализует application port во внешнем слое. Старые `ProjectService` и
`ProjectReportService` были активными, но misplaced; после переноса единственных
production callers они удалены, а реализация не дублируется.

**Phase 5A COMPLETE; Phase 5B COMPLETE; Phase 5 NOT COMPLETE.** Публичный whole-state контракт
`AssessmentDomainState` / `replace_for_domain()` пока сохранён, но его реализация
теперь синхронизирует существующий relational graph на месте. Удаление и повторное
создание `AssessmentWorkspace` устранено; workspace и неизменившиеся дочерние
сущности/ревизии сохраняют DB PK, а rollback остаётся транзакционным. Whole-state
loading и compatibility save пока остаются; ordinary UI writes уже focused.
Остаётся риск same-entity concurrency/lost updates.

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
| `repositories/mine_repository.py` | COMPATIBILITY_ONLY | вызывается только старым `DirectoryDialog`; обычный Project flow использует infrastructure adapter `SqlAlchemyProjectCreation` |
| `services/*.py` | ACTIVE_BUT_MISPLACED | активные workflow/service-фасады, будущий `application/`; DB-specific детали затем отделить |
| `reports/*.py` | ACTIVE_BUT_MISPLACED | активный Excel I/O, будущий `infrastructure/reports/` |
| `ui/pages/*`, `ui/dialogs/*`, `ui/editors/*`, `ui/widgets/plan_view.py`, обычные `ui/*.py` | ACTIVE | нормальная навигация/presentation, кроме явно перечисленных переходных контейнеров |
| `ui/pages/entity_page_controller.py` | ACTIVE_BUT_MISPLACED | активный persistence/application coordinator внутри UI |
| `ui/editors/assessment_geometry_editor.py` | ACTIVE | focused plan editor для создания и ревизии границ Area |
| `ui/dialogs/assessment_candidate_dialog.py`, `blast_event_dialog.py` | ACTIVE | извлечённые production dialogs |
| удалённые workspace/prototype UI/DirectoryDialog | REMOVED | удалены в Phase 2 после извлечения единственных production responsibilities |
| корневой `widgets/*.py` | ACTIVE_BUT_MISPLACED | активные presentation widgets, должны со временем стать `ui/widgets/` |
| `alembic/` | ACTIVE | история текущей схемы и startup/integration checks; не runtime UI |
| `tests/` | ACTIVE | regression safety net, хотя часть тестов структурно связана с legacy |
| старые документы в `docs/` | ACTIVE | инженерная/операционная документация, не executable dependencies |

Phase 1 доказал, что `ui/directory_dialog.py` был DEAD, а
`ui/prototype_2d/blast_event_window.py` и `prototype_2d/blast_event_storage.py` —
COMPATIBILITY_ONLY. Phase 2 удалила их вместе с тестами, которые
проверяли только standalone wrapper/JSON persistence. Production и packaging
callers не было; product coverage перенесено на focused editor/dialogs.

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


## Phase 2: focused Assessment UI

`AssessmentAreaCreationPage` теперь напрямую создаёт `EntityPageController` и
`AssessmentGeometryEditorWidget`. Editor владеет своей scene/plan view, Project
Lines/grid, drawing/refinement handles, candidate preview и командами
`start_new_area`, `start_edit`, `undo_vertex`, `finish_polygon`,
`confirm_boundaries`, `cancel_workflow`. После успешного `create_area`/`revise_area`
он обновляет linked-event suggestions, вызывает controller save и только затем
эмитит ID Area. Hidden workspace и reparenting больше нет.

Удалены `ui/pages/assessment_workspace_page.py`,
`ui/widgets/assessment_workspace.py`, весь `ui/prototype_2d`,
`prototype_2d/blast_event_storage.py` и dead `ui/directory_dialog.py`.
`BlastEventDialog` и `AssessmentCandidateDialog` извлечены в `ui/dialogs/`. Старые
workspace-only links/dataset/dialog/card UI не переносились: normal AreaPage и
Project dashboard уже являются их production UI.

Оставшиеся модули `prototype_2d` — активный domain/application/infrastructure debt
для Phase 3. Оркестрация `MainWindow`, `EntityPageController` и replace-all
`AssessmentStateRepository` намеренно отложены до Phase 4/5.

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

Классификация кода на входе в 5A: repository и mapper **active, но misplaced**
(остаются в старом верхнеуровневом package ради малого безопасного diff);
`infrastructure.db.assessment_state` и session-aware production adapter **active**;
application port и `AssessmentEditingSession` **active**; публичные whole-state
`replace_for_domain*` / `AssessmentStatePersistence.save` **compatibility-only, но
active** до 5B/5C. Dead persistence paths в затронутом графе не обнаружены и
активная совместимость не удалялась.

В Phase 5A `replace_for_domain()` по-прежнему валидирует полный
`AssessmentDomainState` и сохраняет один round-trip contract. Внутри транзакции
`replace_for_domain_in_session()` получает или один раз создаёт Workspace, затем
явно сопоставляет events, areas, revisions, cards, evaluations, links и attachments
по стабильным строковым domain ID. Найденные строки обновляются, новые вставляются,
а отсутствующие удаляются в порядке leaf/dependent → container → revision → parent.
Перед переносом active revision старые active-флаги очищаются отдельным flush, что
не нарушает partial unique indexes. После sync граф перечитывается до commit.

Project Lines остаются Site-wide history: repository только проверяет ссылки и не
переписывает dataset rows. BlastBlock остаётся внешним к workspace graph: sync может
обновить только FK события, но не lifecycle или engineering data блока. Исключение
откатывает все in-place изменения вместе с Block/audit вызывающей транзакции.
Главный оставшийся риск — whole-state lost update при параллельном редактировании;
Phase 5A не добавляет version/concurrency token и не притворяется, что решает его.

### Phase 5B: focused Assessment writes

Обычные UI-команды теперь идут через framework-free порт
`AssessmentWrites` и SQLAlchemy-адаптер `SqlAlchemyAssessmentWrites`. Архивирование,
новые ревизии геометрии, Technical Card и Evaluation, links и attachment metadata
изменяют только относящиеся к команде строки. Составные операции (geometry + links,
Evaluation owner + attachment, Production Block + event + geometry + audit) имеют
одну узкую транзакцию. Живой `AssessmentDomainState` после записи не заменяется,
поэтому ссылки UI на объекты остаются стабильными.

Whole-state load пока остаётся обычным read path. Whole-state `save()` и
`replace_for_domain()` помечены compatibility-only и сохраняются до 5C, но обычные
интерактивные workflow их не вызывают. Это уменьшает перезапись разных сущностей,
но stale write одной и той же сущности пока остаётся last-writer-wins.

Attachment import передаёт весь выбранный пользователем batch одной focused
операции: metadata всех файлов и lazy Evaluation owner коммитятся или откатываются
вместе. Link writes ограничены одной активной/new Area geometry revision;
исторические links не синхронизируются из живого графа. Каждый focused writer
дополнительно проверяет Domain/Workspace и relational owner, поэтому logical ID из
другого Domain не может изменить Evaluation, attachment, card или link.

Fallback whole-state write в `AssessmentEditingSession._write()` оставлен только
для старых unit tests/programmatic embedders, которые создают session напрямую.
Desktop factory всегда передаёт `SqlAlchemyAssessmentWrites`; это закреплено
architecture-тестом.

**Phase 5C** должна: (1) добавить optimistic version/token; (2) обнаруживать stale
same-entity/workspace edits; (3) убрать совместимый whole-state normal-save API;
(4) удалить `replace_for_domain()` после исчезновения потребителей; (5) удалить
оставшийся transitional persistence; (6) закрепить итоговые architecture ratchets.

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

* `Mine -> Site` — историческая пара. Новый project creation adapter создаёт обе строки с
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
UI файла, два Qt-долга (`entity_attachments.py` и compatibility storage) и восемь
Mine-compatibility файлов.
Baseline — код, а не огромный snapshot imports; его следует только сокращать.

## Phase 3A: geometry core и import adapters (завершена)

Phase 3A перенесла без изменения алгоритмов единые `Plan*` и Datamine value types
в `domain/geometry/types.py`, чистые операции — в
`domain/geometry/operations.py`, построение Domain footprint — в
`domain/project/domain_geometry.py`. CSV, DXF и их dispatch теперь находятся в
`infrastructure/geometry_import/`. Старые семь geometry/import модулей
`prototype_2d` удалены, и architecture test запрещает их восстановление.

`blast_geometry.py` фактически не выполнял I/O: он преобразовывал уже разобранные
`DatamineLine`. Поэтому весь модуль стал чистой policy
`domain/geometry/blast.py`; искусственный пустой `infrastructure/.../blast.py` не
создавался. `prototype_2d/domain.py` временно re-export-ит канонические geometry
типы, потому что Phase 3B ещё должна перенести сериализуемые BlastEvent,
AssessmentArea и AssessmentDomainState. Это единственный compatibility bridge и
в нём нет второй реализации.

После переноса `domain.geometry` зависит только от стандартной библиотеки и своих
типов. `infrastructure.geometry_import` зависит от `domain.geometry` и внешнего
`ezdxf`, но не от Qt/UI. Внутренний geometry/import cluster в `prototype_2d`
исчез. Остаётся ранее известный цикл `prototype_2d.domain <->
prototype_2d.technical_card`; его разрыв вместе с сущностями, assessment policy и
attachment Qt/files split относится к Phase 3B/3C. Схема БД, persistence и
MainWindow в Phase 3A не менялись.

## Phase 4A: создание Blast Event (завершена)

Зафиксированная граница до изменения: `BlastBlockService.create_block()` открывал
и коммитил первую транзакцию (Block + audit), затем
`AssessmentStateRepository.replace_for_domain()` открывал и коммитил вторую
транзакцию (replace-all workspace). Если вторая операция падала, `MainWindow`
пытался третьей транзакцией вручную удалить уже сохранённый Block. Поэтому это
была компенсация, а не атомарность.

Phase 4A завершена точечно: `MainWindow` теперь только собирает значения диалога,
вызывает `CreateBlastEvent` и выполняет обновление/навигацию. Use case проверяет
право редактирования, использует прежний `BlastEventService` и работает через
узкий application-port. Contour сохраняется прежним replace-all вызовом без блока.
Production создаёт `BlastBlock`, связывает его с событием, заменяет assessment
state и пишет прежнюю audit-запись в одной SQLAlchemy-транзакции. Ошибка на любом
этапе откатывает обе стороны; UI-компенсация удалением блока устранена.

`AssessmentStateRepository.replace_for_domain()` сохранил публичный контракт и
собственную транзакцию, но делегирует работу в `replace_for_domain_in_session()`;
этот helper не делает commit и позволяет atomic adapter владеть транзакцией.
Replace-all `AssessmentDomainState` и `AssessmentWorkspace` намеренно остаются до
Phase 5. Схема БД и инженерные расчёты не менялись.

## Phase 4B1: entity editing (завершена)

До Phase 4B1 `EntityPageController` сам создавал repository, загружал и сохранял
`AssessmentDomainState`, владел workspace ID, Technical Card/Evaluation services
и тремя видами компенсации: revision, transient Evaluation и lazy attachment
owner. Теперь framework-free `AssessmentStatePersistence` возвращает собственный
application snapshot, а простой SQLAlchemy adapter переводит старый repository
contract в этот port. `AssessmentEditingSession` владеет живым state graph,
draft/save workflows, permission check и rollback. После save граф не заменяется,
поэтому ссылки UI на события, карточки, оценки и ревизии остаются действительными.

`EntityPageController` остался временным UI adapter: создаёт editing session через
composition helper, даёт страницам удобный поиск area/event и пока соединяет
attachments и Linked Events. Replace-all `replace_for_domain()` сохранён без
изменения, как и Technical Card formulas и раздельные DAI/FCI (`X=FCI`, `Y=DAI`).

**Phase 4 завершена в Phase 4C.** Phase 5 включает focused persistence, Unit of Work, concurrency и удаление replace-all persistence.
