# SecureDox Ansible

The Ansible layer demonstrates SSH-based configuration management for a
SecureDox host:

- Linux hardening.
- Docker installation and daemon settings.
- Monitoring agent setup.
- Idempotent playbooks with explicit check mode support.

## Local Check

```bash
ansible-galaxy collection install -r infra/ansible/requirements.yml
ansible-playbook -i infra/ansible/inventories/local.ini infra/ansible/playbooks/check.yml
```

## Apply To A Linux Host

Update inventory with the host and SSH user, then run:

```bash
ansible-playbook -i infra/ansible/inventories/local.ini infra/ansible/playbooks/site.yml --check
ansible-playbook -i infra/ansible/inventories/local.ini infra/ansible/playbooks/site.yml
```

The playbooks are written to be idempotent: re-running should report no changes
unless host drift is detected.
