[![en](https://img.shields.io/badge/lang-en-red.svg)](https://ohara-lab-su.github.io/xdm1000/en/manual/implementation_notes.html) [![ja](https://img.shields.io/badge/lang-ja-blue.svg)](https://ohara-lab-su.github.io/xdm1000/ja/manual/implementation_notes.html)

> **Version note:** Discussion of statistics mode here concerns a previous implementation. The documented current `Xdm1000Ctrl` API does not include `start_statistics_mode()`. Do not treat that section as current usage guidance.


# Implementation Notes

Operational caveats include rejecting configuration and measurement commands during acquisition, cooperative rather than instantaneous stop handling, and host-based timestamps. The process and direct statistics implementations differ. SCPI `RATE` terminology is inconsistent between source layers and requires verification against the instrument. `SERVER_HOST` and `SERVER_IP` also differ across configuration and clients.

> **Documentation scope:** This English guide is an abridged technical companion to the complete Japanese manual. This page is a summary of the supplied Japanese document; consult the Japanese version for details and complete examples.

## Excluded controller methods

## Restrictions during acquisition

## Stopping

## Continuous acquisition timestamps

## Statistics caveats

## RATE inconsistency

## SERVER_HOST and SERVER_IP

## Configuration path resolution
