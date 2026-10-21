package main

import (
	"net/http"
	"net/http/httptest"
	"testing"
)

func TestRedirectToHTTPS(t *testing.T) {
	cases := []struct{ httpsAddr, host, path, want string }{
		{":443", "circuitpath.local", "/teacher?x=1", "https://circuitpath.local/teacher?x=1"},
		{":443", "circuitpath.local:80", "/", "https://circuitpath.local/"},
		{":8443", "localhost:8080", "/projects", "https://localhost:8443/projects"},
	}
	for _, c := range cases {
		req := httptest.NewRequest("GET", "http://"+c.host+c.path, nil)
		req.Host = c.host
		rec := httptest.NewRecorder()
		redirectHandler(c.httpsAddr).ServeHTTP(rec, req)
		if rec.Code != http.StatusMovedPermanently || rec.Header().Get("Location") != c.want {
			t.Errorf("%s%s → %d %q, want %q", c.host, c.path, rec.Code, rec.Header().Get("Location"), c.want)
		}
	}
}
