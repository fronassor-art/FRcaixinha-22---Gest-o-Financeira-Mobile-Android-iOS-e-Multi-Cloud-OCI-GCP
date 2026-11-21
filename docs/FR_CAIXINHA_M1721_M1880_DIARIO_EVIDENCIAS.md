# FR Caixinha AI Studio — M1721–M1880 (160 controles)

**Data:** 04/11/2026. **Base local homologada:** `8f25cfb88fcdd44bb1c891d838eea3ea2a3872f1` (M1720, CI #41895402144 6/6 PASS). Branch `atualizacao-ai-studio-9b46a63187`, PR #2 Draft; projeto AI Studio independente da antiga FRcaixinha 2.2.

## Entrega efetivamente codificada (primeira etapa do M1880)

- `backend/app/synthetic_financial_journal.py`: diário **sintético e puro**, chain SHA-256 determinístico, eventos tipados de aprovação, estorno, chargeback e disputa; valida replay, sequência, mudança de hash, credor, tenant, operação, valor e tempo. O hash é *detectável*, não autenticado por uma entidade externa. Nada grava no banco.
- `backend/app/annual_evidence_preflight.py`: oráculo cadastral para resultado anual; separa contribuições de capital e principal de empréstimos das receitas de juros, mora, multa e despesas/perdas; valida competência em `America/Belem`, unicidade de identificadores e referências, limites de centavos, disputas e ausência de evidências.
- `backend/app/main.py`: endpoint não listado em OpenAPI `GET /api/health/features/m1880`, com flags explícitas de bloqueio, nenhum token/saldo e sem acesso ao banco.
- `backend/tests/test_m1880_financial_evidence_ci.py`: bateria de regressão com muitas combinações sintéticas e invariantes negativos; integrada a `.github/workflows/validacao-atualizacao.yml` para verificação no SHA da nova entrega.

**Limitações de segurança:** todas as provas deste motor são **DECLARADAS**, não verificadas fora do processo. `APPROVED_FIXTURE_ONLY` e `SYNTHETIC_CHAIN_MATCH_ONLY` não atestam extrato do Mercado Pago nem saldo em banco. Hash SHA-256 simples **não** protege contra adulteração por quem controla o log e o hash. Nenhuma função credita valor real, grava contabilidade, autentica comprador, aprova reembolso, faz Pix ou inicia fechamento.

## Entregáveis que seguem pendentes

OAuth Mercado Pago multiempresa; consulta GET e liquidação autoritativa usando tokens de sandbox; inbox SQL transacional com idempotência, RLS e prova de origem; mapeamento de Pix/empréstimos a obrigações; consolidação contábil com reversões; restituição líquida comprovada; aprovação contratual; fechamento real, extratos por papel; Android homologado em aparelho e OCI staging isolado.

## Classificação dos 160 controles

`LOCAL_SINTETICO` significa que existe lógica/teste local ou invariantes já codificados, **sem certificação operacional**; `PENDENTE_OPERACIONAL` significa que a função de negócio integral está faltando. A CI do novo SHA precisa ser verificada antes de declarar os testes PASS. Os 160 IDs contam escopo, não funcionalidades operacionais concluídas.

| ID | Frente | Controle | Estado |
|---|---|---|---|
| M1721 | Diário sintético e cadeia de integridade | Contrato de laboratório M1880 separado de banco | LOCAL_SINTETICO |
| M1722 | Diário sintético e cadeia de integridade | Eventos em dataclass imutável | LOCAL_SINTETICO |
| M1723 | Diário sintético e cadeia de integridade | Sequência positiva | LOCAL_SINTETICO |
| M1724 | Diário sintético e cadeia de integridade | Sequência contígua desde um | LOCAL_SINTETICO |
| M1725 | Diário sintético e cadeia de integridade | Hash SHA-256 canônico | LOCAL_SINTETICO |
| M1726 | Diário sintético e cadeia de integridade | Hash anterior registrado | LOCAL_SINTETICO |
| M1727 | Diário sintético e cadeia de integridade | Hash recalculado no replay | LOCAL_SINTETICO |
| M1728 | Diário sintético e cadeia de integridade | Evento adulterado rejeitado | LOCAL_SINTETICO |
| M1729 | Diário sintético e cadeia de integridade | UUID de evento duplicado rejeitado | LOCAL_SINTETICO |
| M1730 | Diário sintético e cadeia de integridade | Timestamp com fuso obrigatório | LOCAL_SINTETICO |
| M1731 | Diário sintético e cadeia de integridade | Timestamp UTC canonicalizado | LOCAL_SINTETICO |
| M1732 | Diário sintético e cadeia de integridade | Tipos de evento em allowlist | LOCAL_SINTETICO |
| M1733 | Diário sintético e cadeia de integridade | Valores monetários em centavos inteiros | LOCAL_SINTETICO |
| M1734 | Diário sintético e cadeia de integridade | Rejeição de centavos negativos ou fora do limite | LOCAL_SINTETICO |
| M1735 | Diário sintético e cadeia de integridade | Diário limitado a mil eventos | LOCAL_SINTETICO |
| M1736 | Diário sintético e cadeia de integridade | Proveniência bancária NÃO inferida de hash | LOCAL_SINTETICO |
| M1737 | Diário sintético e cadeia de integridade | Assinatura digital externa do diário | PENDENTE_OPERACIONAL |
| M1738 | Diário sintético e cadeia de integridade | Ancoragem de hash fora do banco | PENDENTE_OPERACIONAL |
| M1739 | Diário sintético e cadeia de integridade | Retenção imutável conforme LGPD | PENDENTE_OPERACIONAL |
| M1740 | Diário sintético e cadeia de integridade | Recuperação de cadeia persistida | PENDENTE_OPERACIONAL |
| M1741 | Idempotência e ciclos do provedor | Identidade de operação cotejada | LOCAL_SINTETICO |
| M1742 | Idempotência e ciclos do provedor | Identidade de idempotência cotejada | LOCAL_SINTETICO |
| M1743 | Idempotência e ciclos do provedor | Referência externa de operação única | LOCAL_SINTETICO |
| M1744 | Idempotência e ciclos do provedor | ID de pagamento do provedor único | LOCAL_SINTETICO |
| M1745 | Idempotência e ciclos do provedor | Aprovação sintética única por operação | LOCAL_SINTETICO |
| M1746 | Idempotência e ciclos do provedor | Reembolso sem aprovação rejeitado | LOCAL_SINTETICO |
| M1747 | Idempotência e ciclos do provedor | Reembolso acima do saldo rejeitado | LOCAL_SINTETICO |
| M1748 | Idempotência e ciclos do provedor | Chargeback acima do saldo rejeitado | LOCAL_SINTETICO |
| M1749 | Idempotência e ciclos do provedor | Chargeback repetido rejeitado | LOCAL_SINTETICO |
| M1750 | Idempotência e ciclos do provedor | Disputa aberta mantém bloqueio | LOCAL_SINTETICO |
| M1751 | Idempotência e ciclos do provedor | Timestamp de evento retroativo rejeitado | LOCAL_SINTETICO |
| M1752 | Idempotência e ciclos do provedor | Reversões conservam centavos | LOCAL_SINTETICO |
| M1753 | Idempotência e ciclos do provedor | Webhooks reais em inbox SQL de uso único | PENDENTE_OPERACIONAL |
| M1754 | Idempotência e ciclos do provedor | Deduplicação distribuída entre instâncias | PENDENTE_OPERACIONAL |
| M1755 | Idempotência e ciclos do provedor | Prova GET autenticada após webhook | PENDENTE_OPERACIONAL |
| M1756 | Idempotência e ciclos do provedor | Retry de provedor com backoff e circuit breaker | PENDENTE_OPERACIONAL |
| M1757 | Idempotência e ciclos do provedor | Reclassificação após reversão real | PENDENTE_OPERACIONAL |
| M1758 | Idempotência e ciclos do provedor | Assinatura e validação operacional HMAC | PENDENTE_OPERACIONAL |
| M1759 | Idempotência e ciclos do provedor | Reconsulta de status até liquidação | PENDENTE_OPERACIONAL |
| M1760 | Idempotência e ciclos do provedor | Provas de reembolso parcial no provedor | PENDENTE_OPERACIONAL |
| M1761 | Segregação e extratos financeiros | Diário por caixa sem cruzar tenants | LOCAL_SINTETICO |
| M1762 | Segregação e extratos financeiros | Recebedor numérico obrigatório | LOCAL_SINTETICO |
| M1763 | Segregação e extratos financeiros | Tenant UUID explícito para caixa | LOCAL_SINTETICO |
| M1764 | Segregação e extratos financeiros | Conta plataforma sem tenant | LOCAL_SINTETICO |
| M1765 | Segregação e extratos financeiros | Vinculação de evento a operação pré-registrada | LOCAL_SINTETICO |
| M1766 | Segregação e extratos financeiros | Evento órfão rejeitado | LOCAL_SINTETICO |
| M1767 | Segregação e extratos financeiros | Collector errado rejeitado | LOCAL_SINTETICO |
| M1768 | Segregação e extratos financeiros | Identidade do pagamento verificada | LOCAL_SINTETICO |
| M1769 | Segregação e extratos financeiros | Posição por operação determinística | LOCAL_SINTETICO |
| M1770 | Segregação e extratos financeiros | Somatório de créditos exato | LOCAL_SINTETICO |
| M1771 | Segregação e extratos financeiros | Somatório de reembolsos exato | LOCAL_SINTETICO |
| M1772 | Segregação e extratos financeiros | Somatório de chargebacks exato | LOCAL_SINTETICO |
| M1773 | Segregação e extratos financeiros | Saldo sintético não tratado como caixa disponível | LOCAL_SINTETICO |
| M1774 | Segregação e extratos financeiros | Extrato bancário por tenant integrado | PENDENTE_OPERACIONAL |
| M1775 | Segregação e extratos financeiros | Prova de liquidação por conta recebedora | PENDENTE_OPERACIONAL |
| M1776 | Segregação e extratos financeiros | Livro-razão imutável com lançamento duplo | PENDENTE_OPERACIONAL |
| M1777 | Segregação e extratos financeiros | Estorno contábil em contraparte | PENDENTE_OPERACIONAL |
| M1778 | Segregação e extratos financeiros | Reconciliar crédito e liquidação externa | PENDENTE_OPERACIONAL |
| M1779 | Segregação e extratos financeiros | RLS do histórico de eventos em banco | PENDENTE_OPERACIONAL |
| M1780 | Segregação e extratos financeiros | Trilha de comprovantes para cada membro | PENDENTE_OPERACIONAL |
| M1781 | Crédito, parcelas e pagamentos | Propostas não viram dívida real | LOCAL_SINTETICO |
| M1782 | Crédito, parcelas e pagamentos | Crédito somente desembolsado/inadimplente para prévia | LOCAL_SINTETICO |
| M1783 | Crédito, parcelas e pagamentos | Ordem de parcelas por vencimento | LOCAL_SINTETICO |
| M1784 | Crédito, parcelas e pagamentos | Juros futuros fora da imputação | LOCAL_SINTETICO |
| M1785 | Crédito, parcelas e pagamentos | Juros remuneratórios antes da mora | LOCAL_SINTETICO |
| M1786 | Crédito, parcelas e pagamentos | Mora simples antes da multa | LOCAL_SINTETICO |
| M1787 | Crédito, parcelas e pagamentos | Multa antes do principal | LOCAL_SINTETICO |
| M1788 | Crédito, parcelas e pagamentos | Centavos de imputação conservados | LOCAL_SINTETICO |
| M1789 | Crédito, parcelas e pagamentos | Real pagamento parcelado com comprovante | PENDENTE_OPERACIONAL |
| M1790 | Crédito, parcelas e pagamentos | Histórico de amortizações idempotente | PENDENTE_OPERACIONAL |
| M1791 | Crédito, parcelas e pagamentos | Encargos legais associados à versão aceita | PENDENTE_OPERACIONAL |
| M1792 | Crédito, parcelas e pagamentos | Reversão de quitação sem anatocismo | PENDENTE_OPERACIONAL |
| M1793 | Crédito, parcelas e pagamentos | Baixa de parcela após conciliação bancária | PENDENTE_OPERACIONAL |
| M1794 | Crédito, parcelas e pagamentos | Saldo devedor por evento reconciliado | PENDENTE_OPERACIONAL |
| M1795 | Crédito, parcelas e pagamentos | Diagnóstico de cronograma incompleto | PENDENTE_OPERACIONAL |
| M1796 | Crédito, parcelas e pagamentos | Rejeição de cobrança superior ao vencido | PENDENTE_OPERACIONAL |
| M1797 | Crédito, parcelas e pagamentos | Quitação antecipada sem juros futuros | PENDENTE_OPERACIONAL |
| M1798 | Crédito, parcelas e pagamentos | Status pós-quitação reconciliado | PENDENTE_OPERACIONAL |
| M1799 | Crédito, parcelas e pagamentos | Testes no dispositivo para parcela e extrato | PENDENTE_OPERACIONAL |
| M1800 | Crédito, parcelas e pagamentos | Autorização independente para desembolso | PENDENTE_OPERACIONAL |
| M1801 | Saída e restituição do membro | Tenant e vínculo exigidos na prévia | LOCAL_SINTETICO |
| M1802 | Saída e restituição do membro | Capital cadastrado não equivale a banco | LOCAL_SINTETICO |
| M1803 | Saída e restituição do membro | Dívida de empréstimo evidenciada separadamente | LOCAL_SINTETICO |
| M1804 | Saída e restituição do membro | Contestação contabilizada separadamente | LOCAL_SINTETICO |
| M1805 | Saída e restituição do membro | Referências de três revisões declaradas | LOCAL_SINTETICO |
| M1806 | Saída e restituição do membro | Revisão duplicada rejeitada | LOCAL_SINTETICO |
| M1807 | Saída e restituição do membro | Restituição líquida permanece nula | LOCAL_SINTETICO |
| M1808 | Saída e restituição do membro | Compensação automática permanece bloqueada | LOCAL_SINTETICO |
| M1809 | Saída e restituição do membro | Contrato aceito por membro e ciclo identificado | PENDENTE_OPERACIONAL |
| M1810 | Saída e restituição do membro | Conciliação real de aportes de capital | PENDENTE_OPERACIONAL |
| M1811 | Saída e restituição do membro | Revisão de dívida contestada | PENDENTE_OPERACIONAL |
| M1812 | Saída e restituição do membro | Revisão independente com identidade assinada | PENDENTE_OPERACIONAL |
| M1813 | Saída e restituição do membro | Direitos ao capital preservados na saída | PENDENTE_OPERACIONAL |
| M1814 | Saída e restituição do membro | Valor devido confirmado por instituições | PENDENTE_OPERACIONAL |
| M1815 | Saída e restituição do membro | Simulação de calendário de restituição | PENDENTE_OPERACIONAL |
| M1816 | Saída e restituição do membro | Pagamento Pix de saída somente após autorização | PENDENTE_OPERACIONAL |
| M1817 | Saída e restituição do membro | Comprovante de restituição conciliado | PENDENTE_OPERACIONAL |
| M1818 | Saída e restituição do membro | Revogação e estorno com motivo e documento | PENDENTE_OPERACIONAL |
| M1819 | Saída e restituição do membro | Notificação individual segura | PENDENTE_OPERACIONAL |
| M1820 | Saída e restituição do membro | Tratamento jurídico de desligamento e sanções | PENDENTE_OPERACIONAL |
| M1821 | Fechamento anual e resultado | Data do evento convertida em America/Belem | LOCAL_SINTETICO |
| M1822 | Fechamento anual e resultado | Período anual parametrizado | LOCAL_SINTETICO |
| M1823 | Fechamento anual e resultado | Período acima de 367 dias rejeitado | LOCAL_SINTETICO |
| M1824 | Fechamento anual e resultado | Receita de juros diferenciada | LOCAL_SINTETICO |
| M1825 | Fechamento anual e resultado | Receita de mora diferenciada | LOCAL_SINTETICO |
| M1826 | Fechamento anual e resultado | Receita de multas diferenciada | LOCAL_SINTETICO |
| M1827 | Fechamento anual e resultado | Despesas elegíveis subtraídas | LOCAL_SINTETICO |
| M1828 | Fechamento anual e resultado | Perdas documentais subtraídas | LOCAL_SINTETICO |
| M1829 | Fechamento anual e resultado | Reversão de receita subtraída | LOCAL_SINTETICO |
| M1830 | Fechamento anual e resultado | Capital de cotas segregado do lucro | LOCAL_SINTETICO |
| M1831 | Fechamento anual e resultado | Principal de empréstimo segregado do lucro | LOCAL_SINTETICO |
| M1832 | Fechamento anual e resultado | Resultados negativos não viram lucro positivo | LOCAL_SINTETICO |
| M1833 | Fechamento anual e resultado | Referência de ledger duplicada rejeitada | LOCAL_SINTETICO |
| M1834 | Fechamento anual e resultado | Comprovante de provedor duplicado rejeitado | LOCAL_SINTETICO |
| M1835 | Fechamento anual e resultado | Disputa sem evento original rejeitada | LOCAL_SINTETICO |
| M1836 | Fechamento anual e resultado | Falta de comprovante registrada | LOCAL_SINTETICO |
| M1837 | Fechamento anual e resultado | Rateio capital-dias com dados conciliados | PENDENTE_OPERACIONAL |
| M1838 | Fechamento anual e resultado | Remuneração admin 15% somente no lucro elegível | PENDENTE_OPERACIONAL |
| M1839 | Fechamento anual e resultado | Reservas e maiores restos auditáveis | PENDENTE_OPERACIONAL |
| M1840 | Fechamento anual e resultado | Fechamento real depende de prova bancária | PENDENTE_OPERACIONAL |
| M1841 | API, Android, acesso e segurança | Contrato de saúde M1880 somente leitura | LOCAL_SINTETICO |
| M1842 | API, Android, acesso e segurança | Rota de contrato fora do OpenAPI | LOCAL_SINTETICO |
| M1843 | API, Android, acesso e segurança | Resposta de saúde sem tokens | LOCAL_SINTETICO |
| M1844 | API, Android, acesso e segurança | Resposta de saúde sem dados financeiros | LOCAL_SINTETICO |
| M1845 | API, Android, acesso e segurança | Bloqueios reais explícitos no contrato | LOCAL_SINTETICO |
| M1846 | API, Android, acesso e segurança | No-store na rota de saúde | LOCAL_SINTETICO |
| M1847 | API, Android, acesso e segurança | Consulta autenticada do diário por tenant | PENDENTE_OPERACIONAL |
| M1848 | API, Android, acesso e segurança | Master sem acesso ao financeiro do tenant | PENDENTE_OPERACIONAL |
| M1849 | API, Android, acesso e segurança | Membro apenas posição financeira própria | PENDENTE_OPERACIONAL |
| M1850 | API, Android, acesso e segurança | Administrador apenas tenant ativo | PENDENTE_OPERACIONAL |
| M1851 | API, Android, acesso e segurança | Painel Android de eventos conciliados | PENDENTE_OPERACIONAL |
| M1852 | API, Android, acesso e segurança | Indicador visual de prova faltante | PENDENTE_OPERACIONAL |
| M1853 | API, Android, acesso e segurança | Indicador de disputa na saída | PENDENTE_OPERACIONAL |
| M1854 | API, Android, acesso e segurança | Estado de conexão e retry sem perder sessão | PENDENTE_OPERACIONAL |
| M1855 | API, Android, acesso e segurança | Proteção contra replay HTTP real | PENDENTE_OPERACIONAL |
| M1856 | API, Android, acesso e segurança | Controle de sessões e RLS das leituras | PENDENTE_OPERACIONAL |
| M1857 | API, Android, acesso e segurança | Homologação de extrato e paginação no APK | PENDENTE_OPERACIONAL |
| M1858 | API, Android, acesso e segurança | Homologação de retorno de recursos offline | PENDENTE_OPERACIONAL |
| M1859 | API, Android, acesso e segurança | Testes de acessibilidade do painel | PENDENTE_OPERACIONAL |
| M1860 | API, Android, acesso e segurança | Testes de atualização do APK instalado | PENDENTE_OPERACIONAL |
| M1861 | CI, OCI e governança | Testes de 250 pagamentos sintéticos exatos | LOCAL_SINTETICO |
| M1862 | CI, OCI e governança | Testes de 200 reembolsos parciais | LOCAL_SINTETICO |
| M1863 | CI, OCI e governança | Testes de 150 adulterações de hash | LOCAL_SINTETICO |
| M1864 | CI, OCI e governança | Testes de 250 receitas anuais | LOCAL_SINTETICO |
| M1865 | CI, OCI e governança | Testes de 250 perdas anuais | LOCAL_SINTETICO |
| M1866 | CI, OCI e governança | Testes de duplicidade e replay | LOCAL_SINTETICO |
| M1867 | CI, OCI e governança | Testes de UTC e fuso Belém | LOCAL_SINTETICO |
| M1868 | CI, OCI e governança | Testes de prova de saída | LOCAL_SINTETICO |
| M1869 | CI, OCI e governança | Teste de contrato FastAPI M1880 | LOCAL_SINTETICO |
| M1870 | CI, OCI e governança | CI backend inclui nova suíte | LOCAL_SINTETICO |
| M1871 | CI, OCI e governança | CI PostgreSQL 16 descartável preservada | PENDENTE_OPERACIONAL |
| M1872 | CI, OCI e governança | CI PostgreSQL 18 descartável preservada | PENDENTE_OPERACIONAL |
| M1873 | CI, OCI e governança | CI frontend preservada | PENDENTE_OPERACIONAL |
| M1874 | CI, OCI e governança | CI APK debug preservada | PENDENTE_OPERACIONAL |
| M1875 | CI, OCI e governança | ZIP fonte AI Studio preservado | PENDENTE_OPERACIONAL |
| M1876 | CI, OCI e governança | PR #2 mantida Draft e sem merge | PENDENTE_OPERACIONAL |
| M1877 | CI, OCI e governança | Sem migração do banco local 5433 | PENDENTE_OPERACIONAL |
| M1878 | CI, OCI e governança | OCI staging isolado com TLS/Vault | PENDENTE_OPERACIONAL |
| M1879 | CI, OCI e governança | Restauração e teste de carga OCI | PENDENTE_OPERACIONAL |
| M1880 | CI, OCI e governança | Autorização jurídica e operacional antes de dinheiro real | PENDENTE_OPERACIONAL |

**Contagem da matriz:** 160 IDs. 89 com lógica/teste local sintético; 71 pendentes de integração operacional. Não interpretar esta contagem como certificação dos sistemas financeiros.

## Checklist de liberação (não satisfeito por esta entrega)

1. GitHub Actions **6/6 PASS** no SHA exato; nenhuma regressão de RBAC/RLS e APk.
2. Evidência assinada/obtenção por canal autenticado da conta Mercado Pago correta e confirmação definitiva, com PSP e timestamps verificados.
3. Banco em staging com migrações auditadas/aprovadas, registros imutáveis, transações atômicas e isolamento por tenant; **não** aplicar essas migrações no Termux 5433 sem aprovação.
4. Reconciliação contábil, contestação, estorno e recebedor verificados por evidência externa; nenhuma proposta de empréstimo ou juros futuros passa como dívida líquida.
5. Verificação documental das obrigações dos membros, revisão independente e autorização jurídica/operacional antes de descontos, restituições ou sanções.
6. OCI segregado e APK homologado no aparelho antes de qualquer decisão de go-live.

## Invariantes permanentes

PR #2 segue Draft, **sem merge nem force push**. Local PostgreSQL `5433` intocado; sem migrações novas, sem operações financeiras reais, sem confundir API/SQL/fixture com confirmação bancária; não reutilizar ambiente FRcaixinha 2.2 privado.

## Comandos de validação na sincronização local (após CI)

`PYTHONPATH=backend python3 -m pytest -q backend/tests/test_m1880_financial_evidence_ci.py`

`curl -fsS http://127.0.0.1:8000/api/health/features/m1880` (requer FastAPI reiniciado no SHA novo).