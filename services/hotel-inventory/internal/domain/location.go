package domain

type Location struct {
	CityCode   string `json:"city_code"`
	CityName   string `json:"city_name"`
	CountyCode string `json:"county_code"`
	CountyName string `json:"county_name"`
}
