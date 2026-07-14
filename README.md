# SlopeForge

Open-source desktop application for building an empirical knowledge base of blasting parameters and final wall quality in open-pit mining.

![GitHub Release](https://img.shields.io/github/v/release/Tinuvael/SlopeForge)
![License](https://img.shields.io/github/license/Tinuvael/SlopeForge)

## Download

Download the latest release from the **Releases** page.

➡ https://github.com/Tinuvael/SlopeForge/releases/latest

## Features

- Blast block database
- Rock mass parameter management
- Blast design parameter management
- Final wall quality assessment
- Photo and document attachment
- Advanced filtering and search
- Empirical case history database
- Data export

## Roadmap

Planned features include:

- Similar blast block search
- Statistical analysis
- Engineering dashboards
- Empirical blasting parameter recommendations
- AI-assisted engineering search
- GIS integration

## Disclaimer

SlopeForge is an engineering data management and decision-support tool.

The software is intended to assist engineers in collecting, organizing, and analyzing empirical blasting data. It does not replace professional engineering judgement, site-specific investigations, or engineering design. Users are responsible for verifying all engineering decisions and ensuring that the selected blasting parameters are appropriate for their specific conditions.

## PostgreSQL database foundation

The MVP database foundation uses PostgreSQL, SQLAlchemy 2.x, psycopg 3, Alembic, environment variables, and Argon2 password hashing.

See the setup guide: [docs/database_setup.md](docs/database_setup.md).
