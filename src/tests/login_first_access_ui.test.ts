/* Verifica primeiro acesso visivel e sem endpoint ficticio de cadastro. */
import assert from 'node:assert/strict';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { readFileSync } from 'node:fs';
import { LoginView } from '../components/LoginView';

const html = renderToStaticMarkup(
  React.createElement(LoginView, {onLoginSuccess: () => undefined})
);
assert.match(html, /Entrar na sua conta/);
assert.match(html, /Primeiro acesso/);
assert.match(html, /Um login para Master, Administrador ou Membro/);
assert.doesNotMatch(html, /Contrato Técnico Mestre/);
assert.doesNotMatch(html, /Governança Técnica &amp; Conformidade/);
const source = readFileSync('src/components/LoginView.tsx','utf8');
assert.match(source, /Sou novo membro/);
assert.match(source, /Quero administrar uma caixinha/);
assert.match(source, /convites eletrônicos/);
assert.match(source, /a ativação por e-mail/);
assert.match(source, /Não é possível criar a conta diretamente/);
assert.ok(!source.includes('authService.register('));
assert.ok(!source.includes('authService.createInvitation('));
assert.match(source, /authService.login\(email.trim\(\), password\)/);
console.log('PASS: login unico compacto e rotas informativas sem cadastro publico');
