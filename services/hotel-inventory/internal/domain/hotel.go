package domain

import (
	"time"

	"github.com/google/uuid"
)

type HotelRating string

const (
	RatingOneStar   HotelRating = "one_star"
	RatingTwoStar   HotelRating = "two_star"
	RatingThreeStar HotelRating = "three_star"
	RatingFourStar  HotelRating = "four_star"
	RatingFiveStar  HotelRating = "five_star"
	RatingUnrated   HotelRating = "unrated"
)

type RoomType string

const (
	RoomSingle    RoomType = "single"
	RoomDouble    RoomType = "double"
	RoomTwin      RoomType = "twin"
	RoomSuite     RoomType = "suite"
	RoomDeluxe    RoomType = "deluxe"
	RoomPenthouse RoomType = "penthouse"
)

type Hotel struct {
	HotelCode   string      `json:"hotel_code"`
	Name        string      `json:"name"`
	Rating      HotelRating `json:"rating"`
	Address     string      `json:"address,omitempty"`
	PinCode     string      `json:"pin_code,omitempty"`
	Lat         *float64    `json:"lat,omitempty"`
	Lng         *float64    `json:"lng,omitempty"`
	Phone       string      `json:"phone,omitempty"`
	Fax         string      `json:"fax,omitempty"`
	WebsiteURL  string      `json:"website_url,omitempty"`
	Facilities  string      `json:"facilities,omitempty"`
	Description string      `json:"description,omitempty"`
	Attractions string      `json:"attractions,omitempty"`
	CityCode    string      `json:"city_code"`
	CreatedAt   time.Time   `json:"created_at"`
	UpdatedAt   time.Time   `json:"updated_at"`
}

type Room struct {
	ID         uuid.UUID `json:"id"`
	HotelCode  string    `json:"hotel_code"`
	RoomNumber string    `json:"room_number"`
	RoomType   RoomType  `json:"room_type"`
	Capacity   int16     `json:"capacity"`
	BasePrice  string    `json:"base_price"`
	Currency   string    `json:"currency"`
	Amenities  []string  `json:"amenities"`
	IsActive   bool      `json:"is_active"`
	CreatedAt  time.Time `json:"created_at"`
	UpdatedAt  time.Time `json:"updated_at"`
}
