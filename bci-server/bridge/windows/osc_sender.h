#pragma once

bool osc_init(const char* ip, int port);
void osc_send(const char* address, const float* values, int count);
void osc_close();
