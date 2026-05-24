package handler_test

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/google/uuid"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"

	"github.com/hotel-ai/booking-ops/internal/config"
	"github.com/hotel-ai/booking-ops/internal/domain"
	"github.com/hotel-ai/booking-ops/internal/handler"
)

// --- fixtures ---

var (
	fixedGuestID   = uuid.MustParse("00000000-0000-0000-0000-000000000001")
	fixedRoomID    = uuid.MustParse("00000000-0000-0000-0000-000000000002")
	fixedBookingID = uuid.MustParse("00000000-0000-0000-0000-000000000003")

	fixedBooking = domain.Booking{
		ID:           fixedBookingID,
		GuestID:      fixedGuestID,
		HotelCode:    "HTL001",
		RoomID:       fixedRoomID,
		CheckInDate:  time.Date(2025, 6, 1, 0, 0, 0, 0, time.UTC),
		CheckOutDate: time.Date(2025, 6, 5, 0, 0, 0, 0, time.UTC),
		TotalPrice:   "450.00",
		Currency:     "USD",
		Status:       domain.StatusPending,
		Version:      1,
	}
)

var testCfg = config.Config{PaginationDefault: 20, PaginationMax: 100}

// newTestRouter wires stubs into the real Chi router so URL routing is exercised.
func newTestRouter(guests *stubGuests, bookings *stubBookings, events *stubEvents) http.Handler {
	return handler.NewRouter(testCfg, guests, bookings, events)
}

func jsonBody(v any) []byte {
	b, _ := json.Marshal(v)
	return b
}

func decodeBody(t *testing.T, w *httptest.ResponseRecorder, dst any) {
	t.Helper()
	require.NoError(t, json.NewDecoder(w.Body).Decode(dst))
}

func boolPtr(b bool) *bool { return &b }

// --- TestCreateBooking ---

func TestCreateBooking(t *testing.T) {
	validReq := map[string]any{
		"guest_id":       fixedGuestID,
		"hotel_code":     "HTL001",
		"room_id":        fixedRoomID,
		"check_in_date":  "2025-06-01",
		"check_out_date": "2025-06-05",
		"total_price":    "450.00",
		"currency":       "USD",
	}

	okAvailability := func(_ context.Context, _ uuid.UUID, _, _ time.Time) (int64, error) { return 0, nil }
	okCreate := func(_ context.Context, b domain.Booking) (domain.Booking, error) {
		b.ID = fixedBookingID
		b.Status = domain.StatusPending
		b.Version = 1
		return b, nil
	}
	noopEvent := func(_ context.Context, _ uuid.UUID, _ string, _ any, _ string) (domain.BookingEvent, error) {
		return domain.BookingEvent{}, nil
	}

	tests := []struct {
		name       string
		body       []byte
		bookings   *stubBookings
		events     *stubEvents
		wantStatus int
	}{
		{
			name:       "creates booking and returns 201",
			body:       jsonBody(validReq),
			bookings:   &stubBookings{checkAvailability: okAvailability, create: okCreate},
			events:     &stubEvents{insert: noopEvent},
			wantStatus: http.StatusCreated,
		},
		{
			name:       "missing hotel_code returns 400",
			body:       jsonBody(map[string]any{"total_price": "100.00"}),
			bookings:   &stubBookings{},
			events:     &stubEvents{},
			wantStatus: http.StatusBadRequest,
		},
		{
			name:       "missing total_price returns 400",
			body:       jsonBody(map[string]any{"hotel_code": "HTL001"}),
			bookings:   &stubBookings{},
			events:     &stubEvents{},
			wantStatus: http.StatusBadRequest,
		},
		{
			name:       "invalid check_in_date format returns 400",
			body:       jsonBody(map[string]any{"hotel_code": "HTL001", "total_price": "100.00", "check_in_date": "01/06/2025", "check_out_date": "2025-06-05"}),
			bookings:   &stubBookings{},
			events:     &stubEvents{},
			wantStatus: http.StatusBadRequest,
		},
		{
			name:       "invalid check_out_date format returns 400",
			body:       jsonBody(map[string]any{"hotel_code": "HTL001", "total_price": "100.00", "check_in_date": "2025-06-01", "check_out_date": "not-a-date"}),
			bookings:   &stubBookings{},
			events:     &stubEvents{},
			wantStatus: http.StatusBadRequest,
		},
		{
			name:       "checkout same as checkin returns 400",
			body:       jsonBody(map[string]any{"hotel_code": "HTL001", "total_price": "100.00", "check_in_date": "2025-06-01", "check_out_date": "2025-06-01"}),
			bookings:   &stubBookings{},
			events:     &stubEvents{},
			wantStatus: http.StatusBadRequest,
		},
		{
			name:       "checkout before checkin returns 400",
			body:       jsonBody(map[string]any{"hotel_code": "HTL001", "total_price": "100.00", "check_in_date": "2025-06-05", "check_out_date": "2025-06-01"}),
			bookings:   &stubBookings{},
			events:     &stubEvents{},
			wantStatus: http.StatusBadRequest,
		},
		{
			name: "overlapping booking returns 409",
			body: jsonBody(validReq),
			bookings: &stubBookings{
				checkAvailability: func(_ context.Context, _ uuid.UUID, _, _ time.Time) (int64, error) { return 1, nil },
			},
			events:     &stubEvents{},
			wantStatus: http.StatusConflict,
		},
		{
			name: "availability check error returns 500",
			body: jsonBody(validReq),
			bookings: &stubBookings{
				checkAvailability: func(_ context.Context, _ uuid.UUID, _, _ time.Time) (int64, error) {
					return 0, fmt.Errorf("connection refused")
				},
			},
			events:     &stubEvents{},
			wantStatus: http.StatusInternalServerError,
		},
		{
			name: "create returns ErrConflict propagates as 409",
			body: jsonBody(validReq),
			bookings: &stubBookings{
				checkAvailability: okAvailability,
				create: func(_ context.Context, _ domain.Booking) (domain.Booking, error) {
					return domain.Booking{}, domain.ErrConflict
				},
			},
			events:     &stubEvents{},
			wantStatus: http.StatusConflict,
		},
		{
			name:       "malformed JSON returns 400",
			body:       []byte(`{invalid`),
			bookings:   &stubBookings{},
			events:     &stubEvents{},
			wantStatus: http.StatusBadRequest,
		},
	}

	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			req := httptest.NewRequest(http.MethodPost, "/v1/bookings", bytes.NewReader(tc.body))
			req.Header.Set("Content-Type", "application/json")
			w := httptest.NewRecorder()

			newTestRouter(&stubGuests{}, tc.bookings, tc.events).ServeHTTP(w, req)

			assert.Equal(t, tc.wantStatus, w.Code)
		})
	}

	t.Run("response body contains booking ID and hotel code", func(t *testing.T) {
		req := httptest.NewRequest(http.MethodPost, "/v1/bookings", bytes.NewReader(jsonBody(validReq)))
		req.Header.Set("Content-Type", "application/json")
		w := httptest.NewRecorder()

		newTestRouter(&stubGuests{}, &stubBookings{
			checkAvailability: okAvailability,
			create:            okCreate,
		}, &stubEvents{insert: noopEvent}).ServeHTTP(w, req)

		require.Equal(t, http.StatusCreated, w.Code)
		var got domain.Booking
		decodeBody(t, w, &got)
		assert.Equal(t, fixedBookingID, got.ID)
		assert.Equal(t, "HTL001", got.HotelCode)
		assert.Equal(t, domain.StatusPending, got.Status)
	})

	t.Run("defaults currency to USD when omitted", func(t *testing.T) {
		bodyNoCurrency := map[string]any{
			"guest_id":       fixedGuestID,
			"hotel_code":     "HTL001",
			"room_id":        fixedRoomID,
			"check_in_date":  "2025-06-01",
			"check_out_date": "2025-06-05",
			"total_price":    "450.00",
		}
		var capturedBooking domain.Booking
		req := httptest.NewRequest(http.MethodPost, "/v1/bookings", bytes.NewReader(jsonBody(bodyNoCurrency)))
		req.Header.Set("Content-Type", "application/json")
		w := httptest.NewRecorder()

		newTestRouter(&stubGuests{}, &stubBookings{
			checkAvailability: okAvailability,
			create: func(_ context.Context, b domain.Booking) (domain.Booking, error) {
				capturedBooking = b
				b.ID = fixedBookingID
				return b, nil
			},
		}, &stubEvents{insert: noopEvent}).ServeHTTP(w, req)

		require.Equal(t, http.StatusCreated, w.Code)
		assert.Equal(t, "USD", capturedBooking.Currency)
	})
}

// --- TestGetBooking ---

func TestGetBooking(t *testing.T) {
	tests := []struct {
		name       string
		bookingID  string
		bookings   *stubBookings
		events     *stubEvents
		wantStatus int
	}{
		{
			name:      "returns booking with events",
			bookingID: fixedBookingID.String(),
			bookings: &stubBookings{
				getByID: func(_ context.Context, _ uuid.UUID) (domain.Booking, error) { return fixedBooking, nil },
			},
			events: &stubEvents{
				listByBooking: func(_ context.Context, _ uuid.UUID) ([]domain.BookingEvent, error) {
					return []domain.BookingEvent{{ID: 1, BookingID: fixedBookingID, EventType: "BookingCreated"}}, nil
				},
			},
			wantStatus: http.StatusOK,
		},
		{
			name:       "invalid UUID returns 400",
			bookingID:  "not-a-uuid",
			bookings:   &stubBookings{},
			events:     &stubEvents{},
			wantStatus: http.StatusBadRequest,
		},
		{
			name:      "booking not found returns 404",
			bookingID: fixedBookingID.String(),
			bookings: &stubBookings{
				getByID: func(_ context.Context, _ uuid.UUID) (domain.Booking, error) {
					return domain.Booking{}, domain.ErrNotFound
				},
			},
			events:     &stubEvents{},
			wantStatus: http.StatusNotFound,
		},
		{
			name:      "events fetch error returns 500",
			bookingID: fixedBookingID.String(),
			bookings: &stubBookings{
				getByID: func(_ context.Context, _ uuid.UUID) (domain.Booking, error) { return fixedBooking, nil },
			},
			events: &stubEvents{
				listByBooking: func(_ context.Context, _ uuid.UUID) ([]domain.BookingEvent, error) {
					return nil, fmt.Errorf("db timeout")
				},
			},
			wantStatus: http.StatusInternalServerError,
		},
	}

	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			req := httptest.NewRequest(http.MethodGet, "/v1/bookings/"+tc.bookingID, nil)
			w := httptest.NewRecorder()

			newTestRouter(&stubGuests{}, tc.bookings, tc.events).ServeHTTP(w, req)

			assert.Equal(t, tc.wantStatus, w.Code)
		})
	}

	t.Run("response embeds events array", func(t *testing.T) {
		req := httptest.NewRequest(http.MethodGet, "/v1/bookings/"+fixedBookingID.String(), nil)
		w := httptest.NewRecorder()

		newTestRouter(&stubGuests{}, &stubBookings{
			getByID: func(_ context.Context, _ uuid.UUID) (domain.Booking, error) { return fixedBooking, nil },
		}, &stubEvents{
			listByBooking: func(_ context.Context, _ uuid.UUID) ([]domain.BookingEvent, error) {
				return []domain.BookingEvent{
					{ID: 1, BookingID: fixedBookingID, EventType: "BookingCreated"},
					{ID: 2, BookingID: fixedBookingID, EventType: "BookingStatusUpdated"},
				}, nil
			},
		}).ServeHTTP(w, req)

		require.Equal(t, http.StatusOK, w.Code)
		var got map[string]any
		decodeBody(t, w, &got)
		events, ok := got["events"].([]any)
		require.True(t, ok, "response must contain an events array")
		assert.Len(t, events, 2)
	})
}

// --- TestUpdateBookingStatus ---

func TestUpdateBookingStatus(t *testing.T) {
	validBody := map[string]any{"status": "confirmed", "version": 1}
	noopEvent := func(_ context.Context, _ uuid.UUID, _ string, _ any, _ string) (domain.BookingEvent, error) {
		return domain.BookingEvent{}, nil
	}

	tests := []struct {
		name       string
		bookingID  string
		body       []byte
		bookings   *stubBookings
		events     *stubEvents
		wantStatus int
	}{
		{
			name:      "updates status and returns 200",
			bookingID: fixedBookingID.String(),
			body:      jsonBody(validBody),
			bookings: &stubBookings{
				updateStatus: func(_ context.Context, _ uuid.UUID, _ int32, _ domain.BookingStatus) (domain.Booking, error) {
					updated := fixedBooking
					updated.Status = domain.StatusConfirmed
					updated.Version = 2
					return updated, nil
				},
			},
			events:     &stubEvents{insert: noopEvent},
			wantStatus: http.StatusOK,
		},
		{
			name:       "invalid UUID returns 400",
			bookingID:  "bad-uuid",
			body:       jsonBody(validBody),
			bookings:   &stubBookings{},
			events:     &stubEvents{},
			wantStatus: http.StatusBadRequest,
		},
		{
			name:       "malformed body returns 400",
			bookingID:  fixedBookingID.String(),
			body:       []byte(`{bad json`),
			bookings:   &stubBookings{},
			events:     &stubEvents{},
			wantStatus: http.StatusBadRequest,
		},
		{
			name:       "missing status returns 400",
			bookingID:  fixedBookingID.String(),
			body:       jsonBody(map[string]any{"version": 1}),
			bookings:   &stubBookings{},
			events:     &stubEvents{},
			wantStatus: http.StatusBadRequest,
		},
		{
			name:      "version conflict returns 409",
			bookingID: fixedBookingID.String(),
			body:      jsonBody(validBody),
			bookings: &stubBookings{
				updateStatus: func(_ context.Context, _ uuid.UUID, _ int32, _ domain.BookingStatus) (domain.Booking, error) {
					return domain.Booking{}, domain.ErrVersionConflict
				},
			},
			events:     &stubEvents{},
			wantStatus: http.StatusConflict,
		},
		{
			name:      "booking not found returns 404",
			bookingID: fixedBookingID.String(),
			body:      jsonBody(validBody),
			bookings: &stubBookings{
				updateStatus: func(_ context.Context, _ uuid.UUID, _ int32, _ domain.BookingStatus) (domain.Booking, error) {
					return domain.Booking{}, domain.ErrNotFound
				},
			},
			events:     &stubEvents{},
			wantStatus: http.StatusNotFound,
		},
	}

	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			req := httptest.NewRequest(http.MethodPost, "/v1/bookings/"+tc.bookingID+"/status", bytes.NewReader(tc.body))
			req.Header.Set("Content-Type", "application/json")
			w := httptest.NewRecorder()

			newTestRouter(&stubGuests{}, tc.bookings, tc.events).ServeHTTP(w, req)

			assert.Equal(t, tc.wantStatus, w.Code)
		})
	}

	t.Run("passes version and status to repository", func(t *testing.T) {
		var capturedVersion int32
		var capturedStatus domain.BookingStatus
		req := httptest.NewRequest(http.MethodPost, "/v1/bookings/"+fixedBookingID.String()+"/status",
			bytes.NewReader(jsonBody(map[string]any{"status": "checked_in", "version": 3})))
		req.Header.Set("Content-Type", "application/json")
		w := httptest.NewRecorder()

		newTestRouter(&stubGuests{}, &stubBookings{
			updateStatus: func(_ context.Context, _ uuid.UUID, version int32, status domain.BookingStatus) (domain.Booking, error) {
				capturedVersion = version
				capturedStatus = status
				updated := fixedBooking
				updated.Status = status
				updated.Version = version + 1
				return updated, nil
			},
		}, &stubEvents{insert: func(_ context.Context, _ uuid.UUID, _ string, _ any, _ string) (domain.BookingEvent, error) {
			return domain.BookingEvent{}, nil
		}}).ServeHTTP(w, req)

		require.Equal(t, http.StatusOK, w.Code)
		assert.Equal(t, int32(3), capturedVersion)
		assert.Equal(t, domain.StatusCheckedIn, capturedStatus)
	})
}

// --- TestCheckAvailability ---

func TestCheckAvailability(t *testing.T) {
	tests := []struct {
		name       string
		query      string
		bookings   *stubBookings
		wantStatus int
		wantAvail  *bool
	}{
		{
			name:  "room is available returns available:true",
			query: fmt.Sprintf("room_id=%s&check_in=2025-06-01&check_out=2025-06-05", fixedRoomID),
			bookings: &stubBookings{
				checkAvailability: func(_ context.Context, _ uuid.UUID, _, _ time.Time) (int64, error) { return 0, nil },
			},
			wantStatus: http.StatusOK,
			wantAvail:  boolPtr(true),
		},
		{
			name:  "room has overlaps returns available:false",
			query: fmt.Sprintf("room_id=%s&check_in=2025-06-01&check_out=2025-06-05", fixedRoomID),
			bookings: &stubBookings{
				checkAvailability: func(_ context.Context, _ uuid.UUID, _, _ time.Time) (int64, error) { return 2, nil },
			},
			wantStatus: http.StatusOK,
			wantAvail:  boolPtr(false),
		},
		{
			name:       "missing room_id returns 400",
			query:      "check_in=2025-06-01&check_out=2025-06-05",
			bookings:   &stubBookings{},
			wantStatus: http.StatusBadRequest,
		},
		{
			name:       "invalid room_id returns 400",
			query:      "room_id=not-a-uuid&check_in=2025-06-01&check_out=2025-06-05",
			bookings:   &stubBookings{},
			wantStatus: http.StatusBadRequest,
		},
		{
			name:       "invalid check_in returns 400",
			query:      fmt.Sprintf("room_id=%s&check_in=bad-date&check_out=2025-06-05", fixedRoomID),
			bookings:   &stubBookings{},
			wantStatus: http.StatusBadRequest,
		},
		{
			name:       "invalid check_out returns 400",
			query:      fmt.Sprintf("room_id=%s&check_in=2025-06-01&check_out=bad-date", fixedRoomID),
			bookings:   &stubBookings{},
			wantStatus: http.StatusBadRequest,
		},
		{
			name:  "repository error returns 500",
			query: fmt.Sprintf("room_id=%s&check_in=2025-06-01&check_out=2025-06-05", fixedRoomID),
			bookings: &stubBookings{
				checkAvailability: func(_ context.Context, _ uuid.UUID, _, _ time.Time) (int64, error) {
					return 0, fmt.Errorf("db timeout")
				},
			},
			wantStatus: http.StatusInternalServerError,
		},
	}

	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			req := httptest.NewRequest(http.MethodGet, "/v1/availability?"+tc.query, nil)
			w := httptest.NewRecorder()

			newTestRouter(&stubGuests{}, tc.bookings, &stubEvents{}).ServeHTTP(w, req)

			assert.Equal(t, tc.wantStatus, w.Code)
			if tc.wantAvail != nil {
				var got map[string]any
				decodeBody(t, w, &got)
				assert.Equal(t, *tc.wantAvail, got["available"])
			}
		})
	}
}

// --- TestListBookingsByGuest ---

func TestListBookingsByGuest(t *testing.T) {
	tests := []struct {
		name       string
		guestID    string
		query      string
		bookings   *stubBookings
		wantStatus int
		wantLen    int
	}{
		{
			name:    "returns bookings for guest",
			guestID: fixedGuestID.String(),
			bookings: &stubBookings{
				listByGuest: func(_ context.Context, _ uuid.UUID, _, _ int32) ([]domain.Booking, error) {
					return []domain.Booking{fixedBooking}, nil
				},
			},
			wantStatus: http.StatusOK,
			wantLen:    1,
		},
		{
			name:    "returns empty slice when no bookings",
			guestID: fixedGuestID.String(),
			bookings: &stubBookings{
				listByGuest: func(_ context.Context, _ uuid.UUID, _, _ int32) ([]domain.Booking, error) {
					return []domain.Booking{}, nil
				},
			},
			wantStatus: http.StatusOK,
			wantLen:    0,
		},
		{
			name:       "invalid UUID returns 400",
			guestID:    "not-a-uuid",
			bookings:   &stubBookings{},
			wantStatus: http.StatusBadRequest,
		},
		{
			name:    "repository error returns 500",
			guestID: fixedGuestID.String(),
			bookings: &stubBookings{
				listByGuest: func(_ context.Context, _ uuid.UUID, _, _ int32) ([]domain.Booking, error) {
					return nil, fmt.Errorf("db error")
				},
			},
			wantStatus: http.StatusInternalServerError,
		},
	}

	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			req := httptest.NewRequest(http.MethodGet, "/v1/guests/"+tc.guestID+"/bookings", nil)
			w := httptest.NewRecorder()

			newTestRouter(&stubGuests{}, tc.bookings, &stubEvents{}).ServeHTTP(w, req)

			assert.Equal(t, tc.wantStatus, w.Code)
		})
	}

	t.Run("passes pagination params to repository", func(t *testing.T) {
		var capturedLimit, capturedOffset int32
		req := httptest.NewRequest(http.MethodGet, "/v1/guests/"+fixedGuestID.String()+"/bookings?limit=5&offset=10", nil)
		w := httptest.NewRecorder()

		newTestRouter(&stubGuests{}, &stubBookings{
			listByGuest: func(_ context.Context, _ uuid.UUID, limit, offset int32) ([]domain.Booking, error) {
				capturedLimit = limit
				capturedOffset = offset
				return []domain.Booking{}, nil
			},
		}, &stubEvents{}).ServeHTTP(w, req)

		require.Equal(t, http.StatusOK, w.Code)
		assert.Equal(t, int32(5), capturedLimit)
		assert.Equal(t, int32(10), capturedOffset)
	})

	t.Run("clamps limit to PaginationMax", func(t *testing.T) {
		var capturedLimit int32
		req := httptest.NewRequest(http.MethodGet, "/v1/guests/"+fixedGuestID.String()+"/bookings?limit=999", nil)
		w := httptest.NewRecorder()

		newTestRouter(&stubGuests{}, &stubBookings{
			listByGuest: func(_ context.Context, _ uuid.UUID, limit, _ int32) ([]domain.Booking, error) {
				capturedLimit = limit
				return []domain.Booking{}, nil
			},
		}, &stubEvents{}).ServeHTTP(w, req)

		require.Equal(t, http.StatusOK, w.Code)
		assert.Equal(t, testCfg.PaginationDefault, capturedLimit, "limit above max falls back to default")
	})
}

// --- TestListBookingsByHotel ---

func TestListBookingsByHotel(t *testing.T) {
	tests := []struct {
		name       string
		hotelCode  string
		bookings   *stubBookings
		wantStatus int
	}{
		{
			name:      "returns bookings for hotel",
			hotelCode: "HTL001",
			bookings: &stubBookings{
				listByHotel: func(_ context.Context, _ string) ([]domain.Booking, error) {
					return []domain.Booking{fixedBooking}, nil
				},
			},
			wantStatus: http.StatusOK,
		},
		{
			name:      "returns empty list when no bookings",
			hotelCode: "HTL999",
			bookings: &stubBookings{
				listByHotel: func(_ context.Context, _ string) ([]domain.Booking, error) {
					return []domain.Booking{}, nil
				},
			},
			wantStatus: http.StatusOK,
		},
		{
			name:      "repository error returns 500",
			hotelCode: "HTL001",
			bookings: &stubBookings{
				listByHotel: func(_ context.Context, _ string) ([]domain.Booking, error) {
					return nil, fmt.Errorf("db error")
				},
			},
			wantStatus: http.StatusInternalServerError,
		},
	}

	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			req := httptest.NewRequest(http.MethodGet, "/v1/hotels/"+tc.hotelCode+"/bookings", nil)
			w := httptest.NewRecorder()

			newTestRouter(&stubGuests{}, tc.bookings, &stubEvents{}).ServeHTTP(w, req)

			assert.Equal(t, tc.wantStatus, w.Code)
		})
	}

	t.Run("passes hotel code to repository", func(t *testing.T) {
		var capturedCode string
		req := httptest.NewRequest(http.MethodGet, "/v1/hotels/MY-HOTEL/bookings", nil)
		w := httptest.NewRecorder()

		newTestRouter(&stubGuests{}, &stubBookings{
			listByHotel: func(_ context.Context, code string) ([]domain.Booking, error) {
				capturedCode = code
				return []domain.Booking{}, nil
			},
		}, &stubEvents{}).ServeHTTP(w, req)

		require.Equal(t, http.StatusOK, w.Code)
		assert.Equal(t, "MY-HOTEL", capturedCode)
	})
}
