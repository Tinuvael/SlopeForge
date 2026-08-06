# Ручная проверка Site / Domain / Project Lines

1. Pull branch.
2. Run: `python -m database.cli migrate`.
3. Start SlopeForge.
4. Open directories.
5. Create Site "Pit A".
6. Create Domains "North" and "South".
7. Select North.
8. Import Project Lines Dataset X.
9. Create one BlastEvent and one AssessmentArea.
10. Select South.
11. Verify Dataset X is already available.
12. Create different Domain data in South.
13. Return North and verify North data are isolated.
14. Import Dataset Y and activate it.
15. Verify South also sees Dataset Y as active after reload.
16. Verify Dataset X remains in history.
17. Restart application.
18. Verify Site/Domain/Dataset/Assessment persistence.
19. Verify BlastBlocks belong to the intended Domain.
20. Verify existing Site filters still work.

Project Lines остаются версионируемыми инженерными данными Site. Эта проверка намеренно не включает dashboard и перенос команд создания в Header Add.

## Ограничение downgrade

Старая схема до `20260806_0006` умеет хранить только одну Assessment workspace на Site. Поэтому downgrade детерминированно сохраняет workspace с минимальным ID, переносит в неё доступную историю Project Lines и каскадно удаляет остальные Domain-workspace. Дополнительные Domain-данные при downgrade неизбежно теряются; upgrade существующей базы PR #39 остаётся недеструктивным.
